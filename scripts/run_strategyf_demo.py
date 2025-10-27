# scripts/run_strategyf_demo.py
import logging
import argparse
from pathlib import Path

# اگر نام‌ها در پکیج شما متفاوت است، این ایمپورت‌ها را با ساختار پروژه خودتان هماهنگ کنید
from sim.strategies.strategy_f import StrategyF
from sim.utils.seed import set_seed

# DummyWorld فقط نمونه است؛ اگر کلاس جهان شما نام دیگری دارد (مثلاً Simulator/World)، همان را ایمپورت کنید
try:
    from sim.worlds.dummy import DummyWorld
except Exception:
    # یک دنیای خیلی ساده برای نمایش، اگر DummyWorld ندارید
    class DummyWorld:
        def __init__(self, ticks=100):
            self.tick = 0
            self.max_ticks = ticks
            # تولید چند تسک ساختگی برای هر تیک
            self.tasks = []

        def next_tick(self):
            self.tick += 1
            # هر تیک 3 تسک ساختگی
            for i in range(3):
                self.tasks.append({
                    "id": f"{self.tick}-{i}",
                    "size_kb": 500,
                    "cycles_required": 400_000,
                    "arrival_tick": self.tick,
                    "deadline_tick": self.tick + 8,
                })

        def get_tasks(self):
            # در پروژه‌ی شما ممکن است world.queue یا world.tasks باشد؛ این تابع را با API واقعی هماهنگ کنید
            return list(self.tasks)

        def apply(self, actions):
            # اعمال نتایج تصمیم‌گیری؛ در پروژه‌ی واقعی شما این بخش منابع/صف را به‌روزرسانی می‌کند
            pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log", type=Path, default=Path("sim_run.log"))
    args = parser.parse_args()

    set_seed(args.seed)

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
        handlers=[logging.FileHandler(args.log, mode="w"), logging.StreamHandler()]
    )

    s = StrategyF()
    world = DummyWorld(ticks=args.ticks)

    for _ in range(args.ticks):
        world.next_tick()
        actions = s.tick(world)  # آداپتور میراثی در StrategyF خروجی امن تولید می‌کند
        logging.getLogger("run").info(f"Tick={world.tick} | actions={len(actions.get('tasks', []))}")
        world.apply(actions)

    print(f"Done. Logs written to {args.log}")

if __name__ == "__main__":
    main()
