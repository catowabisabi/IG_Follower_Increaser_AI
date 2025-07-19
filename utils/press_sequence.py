from config import random_reply
import random

comment_to_use_this_time = random.choice(random_reply)


sequence = [
    ['关注'],
    ['更多选项'],
    ['账户简介'],
    ['赞'],
    ['评论'],
    ['搜索输入', 'AI 美女'],
    {
        'method': 'add_comment',
        'param': 'I love your works!！😍'
    }
]

follow_sequence = [
    ['关注'],
    ['赞'],
    ['评论'],
    {
        'method': 'add_comment',
        'param': comment_to_use_this_time
    },
    ['发布']
]

img_info_page_sequence = [
    ['更多选项'],
    ['账户简介']
]

sequence_logout = [
    ['首页'],
    
    ['设置'],
    ['退出']
]


sequence_login=[
    ['切换账户'],

]

sequence_search_keyword=[
    ['切换账户'],
    
]