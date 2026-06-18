from locust import LoadTestShape


class StressShape(LoadTestShape):
    # ступенчатый рост 50 -> 200 -> 500, по 90с
    stages = [
        {"duration": 90, "users": 50, "spawn_rate": 10},
        {"duration": 180, "users": 200, "spawn_rate": 20},
        {"duration": 270, "users": 500, "spawn_rate": 50},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None


class SpikeShape(LoadTestShape):
    # база 20, пики до 500, два цикла
    stages = [
        {"duration": 30, "users": 20, "spawn_rate": 10},
        {"duration": 75, "users": 500, "spawn_rate": 100},
        {"duration": 120, "users": 20, "spawn_rate": 50},
        {"duration": 165, "users": 500, "spawn_rate": 100},
        {"duration": 210, "users": 20, "spawn_rate": 50},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
