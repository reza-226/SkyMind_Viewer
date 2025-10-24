# skymind_mvp.py
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

random.seed(42)

# ---------------------------
# تنظیمات پایه شبیه‌ساز
# ---------------------------
DT_SEC = 1.0           # طول هر Tick
TOTAL_TICKS = 1000     # تعداد Tick برای MVP
TASKS_PER_TICK = (3, 7)  # تعداد وظیفه در هر Tick (min,max)

# وزن‌های تابع هزینه/پاداش
W_LAT = 0.4
W_EN = 0.3
W_SUCC = 0.2
W_VIO = 0.1

# آستانه شهرت برای F
REPUTATION_MIN = 0.5

# پارامترهای ساده شبکه
B = 5e6          # پهنای باند (Hz)
PTX = 0.1        # توان ارسال (W)
N0 = 1e-9        # چگالی نویز (W/Hz)
K_PROC = 1e-11   # ضریب انرژی پردازش
K_TX = 5e-9      # ضریب انرژی انتقال به ازای هر بیت

# ---------------------------
# مدل‌های ساده وظیفه و گره‌ها
# ---------------------------
@dataclass
class Task:
    size_bits: int         # حجم داده ورودی وظیفه (bits)
    cycles: int            # تعداد سیکل CPU مورد نیاز
    deadline_s: float      # مهلت (ثانیه)
    id: int = field(default=0)

@dataclass
class Node:
    name: str
    kind: str              # "MD" / "UAV" / "MEC"
    cpu_hz: float          # فرکانس CPU (cycles/sec)
    reputation: float      # 0..1
    distance_m: float      # فاصله ارتباطی از MD (برای سادگی ثابت)

class Environment:
    def __init__(self):
        # MD (کاربر) پردازش محلی
        self.md = Node("MD", "MD", cpu_hz=1.5e9, reputation=1.0, distance_m=0.0)
        # UAV و MEC ساده
        self.uav = Node("UAV", "UAV", cpu_hz=3e9, reputation=0.6, distance_m=200.0)
        self.mec = Node("MEC", "MEC", cpu_hz=10e9, reputation=0.8, distance_m=1000.0)

    def channel_gain(self, d_m: float) -> float:
        # مدل خیلی ساده: h ~ 1 / d^2
        if d_m <= 0:
            return 1.0
        return 1.0 / (d_m ** 2)

    def rate_bps(self, d_m: float) -> float:
        # نرخ داده با شانون: R = B * log2(1 + SNR)
        h = self.channel_gain(d_m)
        snr = (PTX * h) / (N0 * B)
        return B * math.log2(1.0 + snr)

    def estimate_local(self, task: Task) -> Tuple[float, float]:
        # تأخیر و انرژی پردازش محلی
        latency = task.cycles / self.md.cpu_hz
        energy = K_PROC * task.cycles  # انرژی تقریبی پردازش
        return latency, energy

    def estimate_offload(self, task: Task, dest: Node) -> Tuple[float, float]:
        # انتقال از MD به مقصد + پردازش در مقصد
        r = self.rate_bps(dest.distance_m)
        tx_delay = task.size_bits / r
        proc_delay = task.cycles / dest.cpu_hz
        latency = tx_delay + proc_delay
        # انرژی سیستم: انرژی ارسال + انرژی پردازش در مقصد
        energy_tx = K_TX * task.size_bits
        energy_proc = K_PROC * task.cycles
        energy = energy_tx + energy_proc
        return latency, energy

# ---------------------------
# استراتژی‌ها
# ---------------------------
class StrategyH:
    """Heuristic: انتخاب کنش با کمینه هزینه وزنی (latency + energy) با رعایت ددلاین در صورت امکان."""
    def choose(self, env: Environment, task: Task) -> str:
        actions = ["local", "uav", "mec"]
        costs = {}
        for a in actions:
            if a == "local":
                lat, en = env.estimate_local(task)
            elif a == "uav":
                lat, en = env.estimate_offload(task, env.uav)
            else:
                lat, en = env.estimate_offload(task, env.mec)
            # جریمه نقض ددلاین
            vio = 1.0 if lat > task.deadline_s else 0.0
            cost = W_LAT * lat + W_EN * en + W_VIO * vio
            costs[a] = cost
        # انتخاب بهترین
        return min(costs, key=costs.get)

class StrategyF:
    """Reputation-aware: فیلتر بر اساس شهرت؛ سپس کمینه هزینه مثل H. اگر هیچ مقصد معتبر نبود، local."""
    def __init__(self, rep_min: float):
        self.rep_min = rep_min

    def choose(self, env: Environment, task: Task) -> str:
        candidates = {
            "local": env.md,
            "uav": env.uav if env.uav.reputation >= self.rep_min else None,
            "mec": env.mec if env.mec.reputation >= self.rep_min else None
        }
        costs = {}
        for a, node in candidates.items():
            if node is None:
                continue
            if a == "local":
                lat, en = env.estimate_local(task)
            else:
                lat, en = env.estimate_offload(task, node)
            vio = 1.0 if lat > task.deadline_s else 0.0
            cost = W_LAT * lat + W_EN * en + W_VIO * vio
            costs[a] = cost
        if not costs:
            return "local"
        return min(costs, key=costs.get)

class StrategyD:
    """نسخه سبک یادگیری: Q-یادگیری بدون حالت، اپسیلون-حریصانه روی کنش‌های {local,uav,mec}."""
    def __init__(self, alpha=0.2, gamma=0.9, epsilon=0.1):
        self.q = {"local": 0.0, "uav": 0.0, "mec": 0.0}
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

    def select_action(self) -> str:
        if random.random() < self.epsilon:
            return random.choice(list(self.q.keys()))
        # exploit
        return max(self.q, key=self.q.get)

    def update(self, action: str, reward: float):
        # Q_new = (1-alpha)Q + alpha * reward (بدون حالت و آینده برای MVP)
        self.q[action] = (1 - self.alpha) * self.q[action] + self.alpha * reward

    def choose(self, env: Environment, task: Task) -> str:
        # برای ارزیابی reward نیاز داریم اجرا کنیم، پس ابتدا کنش انتخاب می‌شود
        return self.select_action()

# ---------------------------
# اجرای یک کنش و محاسبه KPI برای یک وظیفه
# ---------------------------
def execute_action(env: Environment, task: Task, action: str) -> Dict[str, float]:
    if action == "local":
        lat, en = env.estimate_local(task)
    elif action == "uav":
        lat, en = env.estimate_offload(task, env.uav)
    else:
        lat, en = env.estimate_offload(task, env.mec)
    success = 1.0 if lat <= task.deadline_s else 0.0
    vio = 1.0 - success
    reward = -W_LAT * lat - W_EN * en + W_SUCC * success - W_VIO * vio
    return {"latency": lat, "energy": en, "success": success, "violation": vio, "reward": reward}

# ---------------------------
# مولد وظیفه ساده
# ---------------------------
def generate_tasks(tick: int, count: int) -> List[Task]:
    tasks = []
    for k in range(count):
        # سایز داده بین 0.5 تا 5 مگابیت
        size_bits = int(random.uniform(5e5, 5e6))
        # سیکل CPU بین 1e8 تا 8e8
        cycles = int(random.uniform(1e8, 8e8))
        # ددلاین بین 0.2 تا 1.5 ثانیه
        deadline = random.uniform(0.2, 1.5)
        tasks.append(Task(size_bits=size_bits, cycles=cycles, deadline_s=deadline, id=(tick * 1000 + k)))
    return tasks

# ---------------------------
# حلقه شبیه‌ساز
# ---------------------------
def run_sim(strategy_name: str = "H"):
    env = Environment()
    strat_h = StrategyH()
    strat_f = StrategyF(REPUTATION_MIN)
    strat_d = StrategyD(alpha=0.2, gamma=0.9, epsilon=0.1)

    # انباشت KPI
    kpi = {"latency": 0.0, "energy": 0.0, "success": 0.0, "violation": 0.0}
    n_tasks = 0

    for t in range(1, TOTAL_TICKS + 1):
        # تولید وظایف
        n = random.randint(TASKS_PER_TICK[0], TASKS_PER_TICK[1])
        tasks = generate_tasks(t, n)

        for task in tasks:
            # انتخاب استراتژی
            if strategy_name == "H":
                action = strat_h.choose(env, task)
            elif strategy_name == "F":
                action = strat_f.choose(env, task)
            elif strategy_name == "D":
                action = strat_d.choose(env, task)
            else:
                action = "local"

            # اجرا و محاسبه KPI
            res = execute_action(env, task, action)
            # اگر D بود، Q-یادگیری را به‌روزرسانی کن
            if strategy_name == "D":
                strat_d.update(action, res["reward"])

            # انباشت
            for k in kpi:
                kpi[k] += res[k]
            n_tasks += 1

        # Tick پیش می‌رود (در MVP حرکت UAV را ساده می‌گیریم)
        # می‌توانیم بعداً زیر-تیک مسیر را اضافه کنیم.

        # گزارش میان‌دوره‌ای هر 200 Tick
        if t % 200 == 0:
            avg_lat = kpi["latency"] / max(1, n_tasks)
            avg_en = kpi["energy"] / max(1, n_tasks)
            succ_ratio = kpi["success"] / max(1, n_tasks)
            vio_ratio = kpi["violation"] / max(1, n_tasks)
            print(f"[Tick {t}] {strategy_name} | avg_lat={avg_lat:.4f}s avg_en={avg_en:.6f}J "
                  f"succ={succ_ratio:.3f} vio={vio_ratio:.3f}")

    # خروجی نهایی
    avg_lat = kpi["latency"] / max(1, n_tasks)
    avg_en = kpi["energy"] / max(1, n_tasks)
    succ_ratio = kpi["success"] / max(1, n_tasks)
    vio_ratio = kpi["violation"] / max(1, n_tasks)
    return {
        "strategy": strategy_name,
        "tasks": n_tasks,
        "avg_latency_s": avg_lat,
        "avg_energy_j": avg_en,
        "success_ratio": succ_ratio,
        "sla_violations_ratio": vio_ratio,
    }

if __name__ == "__main__":
    print("Running SkyMind MVP with 1-second ticks...")
    # اجرای سه سناریو جداگانه برای مقایسه
    res_h = run_sim("H")
    res_f = run_sim("F")
    res_d = run_sim("D")

    print("\nFinal Results:")
    for res in [res_h, res_f, res_d]:
        print(f"{res['strategy']}: "
              f"tasks={res['tasks']} "
              f"avg_latency={res['avg_latency_s']:.4f}s "
              f"avg_energy={res['avg_energy_j']:.6f}J "
              f"success={res['success_ratio']:.3f} "
              f"SLA_violations={res['sla_violations_ratio']:.3f}")
