import time
import random
import functools
import logging

def retry(max_retries=3, delay_range=(1, 3)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logging.warning(f"[Retry] 嘗試 {attempt + 1}/{max_retries} 失敗: {e}")
                    if attempt + 1 == max_retries:
                        raise
                    time.sleep(random.uniform(*delay_range))
        return wrapper
    return decorator
