from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Пример задачи: выполнение каждые 60 секунд
    # scheduler.add_job(your_task_function, 'interval', seconds=60)
    scheduler.start()
    return scheduler