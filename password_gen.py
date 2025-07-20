import random
import string

def generate_password(length=36):
    characters = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    password = ''.join(random.choices(characters, k=length))
    return password

# 使用範例
if __name__ == "__main__":
    pw = generate_password(36)
    print("你的密碼係：", pw)
