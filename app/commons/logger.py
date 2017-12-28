import logging.handlers
import json_log_formatter
formatter = json_log_formatter.JSONFormatter()

logger = logging.getLogger("query")
logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)

logFilePath = "logs/query-log.json"
file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=logFilePath, when='midnight', backupCount=30)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)
