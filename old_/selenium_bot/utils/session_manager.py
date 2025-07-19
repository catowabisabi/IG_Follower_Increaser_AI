# ========== SessionManager ========== #
class SessionManager:
    _instances = {}
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, username, password, chromedriver_path=None, comment_list=None, openai_api_key=None):
        with cls._lock:
            if username not in cls._instances:
                # 每個帳號一個 user-data-dir
                user_data_dir = os.path.join(os.getcwd(), 'user_data', username)
                os.makedirs(user_data_dir, exist_ok=True)
                bot = InstagramBot(
                    username=username,
                    password=password,
                    chromedriver_path=chromedriver_path,
                    comment_list=comment_list,
                    openai_api_key=openai_api_key,
                    user_data_dir=user_data_dir
                )
                cls._instances[username] = bot
            return cls._instances[username]

    @classmethod
    def remove_instance(cls, username):
        with cls._lock:
            if username in cls._instances:
                try:
                    cls._instances[username].quit()
                except Exception:
                    pass
                del cls._instances[username]

    @classmethod
    def all_usernames(cls):
        return list(cls._instances.keys())