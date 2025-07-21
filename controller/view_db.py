import pprint
from class_db import FollowedUserDB
import sqlite3

DB_PATH = 'followed_user.db'

def print_all_users():
    db = FollowedUserDB(DB_PATH)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        print('--- users ---')
        for row in c.execute('SELECT * FROM users'):
            print(row)

def print_all_followed():
    db = FollowedUserDB(DB_PATH)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        print('--- followed ---')
        for row in c.execute('SELECT * FROM followed'):
            print(row)

def main():
    print_all_users()
    print()
    print_all_followed()

if __name__ == '__main__':
    main() 