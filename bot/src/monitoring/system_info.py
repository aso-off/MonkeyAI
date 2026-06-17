import asyncio
import json
import time

from src.core.config import settings
from src.core.logger import logger

SYSTEM_INFO_KEY = "system_info"
SYSTEM_INFO_TTL = 7200   # 2 часа
SYSTEM_INFO_INTERVAL = 1800  # 30 минут


def _stdout(result) -> str:
    out = result.stdout
    if out is None:
        return ""
    return out if isinstance(out, str) else out.decode(errors="replace")


async def _collect_system_info(redis) -> None:
    """Collect docker stats + host metrics via SSH and cache result in Redis."""
    ssh = settings.ssh_connection
    if not ssh.get("hostname"):
        logger.debug("SSH not configured — skipping system info collection")
        return

    import asyncssh
    import yaml as _yaml

    from src.utils.localization import t

    lang = "ru"
    project_path = ssh.get("project_path", "/root/bot")
    container_names: list[str] = settings.container_names
    timeout = ssh.get("timeout", 10)

    def _parse_mem_gb(s: str) -> float:
        s = s.strip()
        try:
            if "GiB" in s:
                return float(s.replace("GiB", "").strip())
            elif "MiB" in s:
                return float(s.replace("MiB", "").strip()) / 1024
            elif "kB" in s:
                return float(s.replace("kB", "").strip()) / (1024 ** 2)
            elif s.endswith("B"):
                return float(s[:-1].strip()) / (1024 ** 3)
        except ValueError:
            pass
        return 0.0

    try:
        async with asyncio.timeout(timeout + 5):
            async with asyncssh.connect(
                ssh["hostname"],
                username=ssh.get("username"),
                password=ssh.get("password"),
                known_hosts=None,
                connect_timeout=timeout,
            ) as conn:
                blocks: list[str] = []

                if container_names:
                    container_cpus: dict[str, float] = {}
                    try:
                        compose_r = await conn.run(f'cat "{project_path}/docker-compose.yml"')
                        compose_data = _yaml.safe_load(_stdout(compose_r))
                        for svc_config in (compose_data or {}).get("services", {}).values():
                            cname = svc_config.get("container_name")
                            cpus_val = svc_config.get("cpus", "0")
                            if cname:
                                try:
                                    container_cpus[cname] = float(str(cpus_val).strip('"'))
                                except ValueError:
                                    container_cpus[cname] = 0.0
                    except Exception as e:
                        logger.warning(f"Could not parse docker-compose.yml for cpus: {e}")

                    fmt = "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}"
                    stats_r = await conn.run(
                        f'docker stats --no-stream --format "{fmt}" 2>/dev/null'
                    )
                    container_blocks: list[str] = []
                    stats_out = _stdout(stats_r)
                    if stats_out.strip():
                        for line in stats_out.strip().splitlines():
                            parts = line.split("|")
                            if len(parts) < 4:
                                continue
                            name, cpu_str, mem_str, net_str = parts[0], parts[1], parts[2], parts[3]
                            if name not in container_names:
                                continue
                            try:
                                cpu_pct = float(cpu_str.replace("%", "").strip())
                            except ValueError:
                                cpu_pct = 0.0
                            mem_used_s, mem_limit_s = (
                                mem_str.split(" / ", 1) if " / " in mem_str else (mem_str, "0B")
                            )
                            net_rx_str, net_tx_str = (
                                net_str.split(" / ", 1) if " / " in net_str else (net_str, "0B")
                            )
                            container_blocks.append(
                                "<pre>"
                                + t("container_info_template", lang).format(
                                    name=name,
                                    cpu_percent=cpu_pct,
                                    cpus=container_cpus.get(name, 0.0),
                                    ram_usage=_parse_mem_gb(mem_used_s),
                                    ram_limit=_parse_mem_gb(mem_limit_s),
                                    net_rx_str=net_rx_str.strip(),
                                    net_tx_str=net_tx_str.strip(),
                                )
                                + "</pre>"
                            )

                    if container_blocks:
                        blocks.append(f"<b>{t('docker_title', lang)}</b>")
                        blocks.extend(container_blocks)

                hostname_r = await conn.run("hostname")
                hostname = _stdout(hostname_r).strip() or "unknown"

                cpu_r = await conn.run(
                    "top -bn1 | grep 'Cpu(s)' | "
                    "sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | "
                    "awk '{print 100 - $1}'"
                )
                try:
                    cpu_pct = float(_stdout(cpu_r).strip())
                except ValueError:
                    cpu_pct = 0.0

                cores_r = await conn.run("nproc")
                try:
                    cores = int(_stdout(cores_r).strip())
                except ValueError:
                    cores = 1

                ram_r = await conn.run(
                    "free | awk 'NR==2{printf \"%.2f %.2f\", $3/1024/1024, $2/1024/1024}'"
                )
                ram_vals = _stdout(ram_r).strip().split()
                ram_used = float(ram_vals[0]) if len(ram_vals) >= 1 else 0.0
                ram_total = float(ram_vals[1]) if len(ram_vals) >= 2 else 0.0

                disk_r = await conn.run(
                    "df -BG / | awk 'NR==2{gsub(/G/,\"\"); print $4, $2}'"
                )
                disk_vals = _stdout(disk_r).strip().split()
                if len(disk_vals) >= 2:
                    disk_free = float(disk_vals[0])
                    disk_total_gb = float(disk_vals[1])
                    disk_used = disk_total_gb - disk_free
                else:
                    disk_used = disk_total_gb = 0.0

                blocks.append(
                    f"<b>{t('host_title', lang)}</b>\n"
                    "<pre>"
                    + t("host_info_template", lang).format(
                        hostname=hostname,
                        cpu_percent=cpu_pct,
                        num_cores=cores,
                        ram_usage=ram_used,
                        ram_total=ram_total,
                        disk_usage=disk_used,
                        disk_total=disk_total_gb,
                    )
                    + "</pre>"
                )

                payload = json.dumps({"timestamp": time.time(), "blocks": blocks})
                await redis.setex(SYSTEM_INFO_KEY, SYSTEM_INFO_TTL, payload)
                logger.info("System info collected and cached")

    except TimeoutError:
        logger.warning("SSH system info collection timed out after %ds", timeout + 5)
    except Exception as e:
        logger.error(f"System info collection error: {e}")


async def _system_info_loop(redis) -> None:
    while True:
        await _collect_system_info(redis)
        await asyncio.sleep(SYSTEM_INFO_INTERVAL)
