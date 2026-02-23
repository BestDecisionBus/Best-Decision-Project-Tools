bind = "0.0.0.0:5050"
workers = 2
timeout = 300
accesslog = "-"
errorlog = "-"


def post_fork(server, worker):
    import task_queue
    task_queue.start_worker()
