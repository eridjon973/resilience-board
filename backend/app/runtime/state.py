import threading


recent_deleted_pods = []
recent_added_pods = []

incidents = []
chaos_history = []

watcher_status = {
    "running": False,
    "started_at": None,
    "last_event_time": None,
    "last_error": None,
    "restart_count": 0,
}

db_lock = threading.Lock()
