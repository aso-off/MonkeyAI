FROM postgres:17-alpine

RUN apk add --no-cache aws-cli

COPY pg_backup.sh /usr/local/bin/pg_backup.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/pg_backup.sh /usr/local/bin/entrypoint.sh \
 && echo '0 11 * * 4 /usr/local/bin/pg_backup.sh > /proc/1/fd/1 2>/proc/1/fd/2' > /etc/crontabs/root

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
