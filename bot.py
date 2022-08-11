import telebot
from config import token
from config import texts
from config import admins
from random import shuffle
import json

bot = telebot.TeleBot(token)

def save():
    with open('data.json', 'w') as f:
        json.dump(data, f)
    return

def get_data():
    with open('data.json') as f:
        d = json.load(f)
        nicks_keys = d['nicks'].keys()
        temp = {}
        for key in nicks_keys:
            temp[int(key)] = d['nicks'][key]
        d['nicks'] = temp 
        
        temp = {}
        stats_keys = d['stats'].keys()
        for key in stats_keys:
            temp[int(key)] = d['stats'][key] 
        d['stats'] = temp
        print(d)
        return d

data = {
    "registered_users": [],
    "nicks": {},
    "hosts": [],
    "host_names": [],
    "games": [],
    "stats": {}
}

data = get_data()

def create_game(id, name):
    game = {
        "name": name,
        "host": id,
        "participants": [
            {
                "id": id,
                "live": True
            }
        ],
        "state": 1,
        "winner": None
    }

    return game

def create_stats(id):
    data['stats'][id] = {
        "wins": 0,
        "kills": 0,
        "deaths": 0
    }

def is_registered(id):
    if id in data['registered_users']:
        return True

    bot.send_message(id, texts['unregistered'])
    return False


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, texts['start_description'])


@bot.message_handler(commands=['help'])
def start_message(message):
    bot.send_message(message.chat.id, texts['help'])

# create game
@bot.message_handler(commands=['host'])
def host_game(message):
    if not is_registered(message.chat.id):
        return

    if message.chat.id in data['hosts']:
        bot.send_message(message.chat.id, texts['not_one_host'])
        return

    my_message = bot.send_message(message.chat.id, texts['host'])
    bot.register_next_step_handler(my_message, set_host_name)

def set_host_name(message):
    name = message.text
    if name in data['host_names']:
        my_message = bot.send_message(message.chat.id, texts['not_unique_host_name'])
        bot.register_next_step_handler(my_message, set_host_name)
        return

    data['hosts'].append(message.chat.id)
    data['host_names'].append(name)
    data['games'].append(create_game(message.chat.id, name))
    bot.send_message(message.chat.id, texts['game_created_successfully'] + name)
    save()

# register user
@bot.message_handler(commands=['register'])
def register(message):
    if message.chat.id in data['registered_users']:
        bot.send_message(message.chat.id, texts['already_registered'])
        return

    my_message = bot.send_message(message.chat.id, texts['nick_question'])
    bot.register_next_step_handler(my_message, set_nick)

# rename user
@bot.message_handler(commands=['rename'])
def rename(message):
    if not is_registered(message.chat.id):
        return
    
    my_message = bot.send_message(message.chat.id, texts['nick_question'])
    bot.register_next_step_handler(my_message, set_nick)

def set_nick(message):
    new_user = True
    if message.chat.id in data['registered_users']:
        new_user = False
        data['nicks'][message.chat.id] = message.text
    
    if new_user:
        data['registered_users'].append(message.chat.id)
        data['nicks'][message.chat.id] = message.text
        create_stats(message.chat.id)
        bot.send_message(message.chat.id, texts['registered_successfully'])
        return save()
    
    bot.send_message(message.chat.id, texts['nick_updated'])
    save()


@bot.message_handler(commands=['participate'])
def participate(message):
    if not is_registered(message.chat.id):
        return

    user_id = message.chat.id
    for game in data['games']:
        for paricipant in game['participants']:
            if user_id == paricipant and game['state'] != 3:
                bot.send_message(user_id, texts['already_plaing'])
                return
    
    my_message = bot.send_message(message.chat.id, texts['enter_game_name'])
    bot.register_next_step_handler(my_message, get_game_name)

def get_game_name(message):
    name = message.text
    user_id = message.chat.id
    for game in data['games']:
        if game['name'] == name:
            if game['state'] != 1:
                bot.send_message(user_id, texts['unavailable_game']) 
                return
            
            game['participants'].append({
                'id': user_id,
                'live': True
            })

            bot.send_message(user_id, texts['participate_successfully'] + game['name'])
            return save()

    bot.send_message(user_id, texts['unavailable_game'])


@bot.message_handler(commands=['start_game'])
def start_game(message):
    if not is_registered(message.chat.id):
        return

    user_id = message.chat.id
    for game in data['games']:
        if game['host'] == user_id and game['state'] == 1:
            shuffle(game['participants'])
            for i in range(len(game['participants'])):
                next = find_next_live(game, i)
                if game['participants'][next % len(game['participants'])]['live']:
                    bot.send_message(game['participants'][i]['id'], texts['game_started'] + game['name'])
                    bot.send_message(game['participants'][i]['id'], texts['target'] + "||" + data['nicks'][game['participants'][next % len(game['participants'])]['id']] + "||", parse_mode='MarkdownV2')
                    i = next

            game['state'] = 2
            return save()
    
    bot.send_message(message.chat.id, "Нечего запускать")

def find_next_live(game, i):
    for j in range(i + 1, i + len(game['participants'])):
        if game['participants'][j % len(game['participants'])]['live']:
            return j
    return 0

def find_previous_live(game, i):
    for j in range(i + len(game['participants']) - 1, i, -1):
        if game['participants'][j % len(game['participants'])]['live']:
            return j
    return 0

@bot.message_handler(commands=['die'])
def die(message):
    if not is_registered(message.chat.id):
        return

    user_id = message.chat.id
    for game in data['games']:
        if game['state'] == 3:
            continue

        for player in game['participants']:
            if player['id'] == user_id:
                remove_user(user_id, game)

    return save()

def remove_user(user_id, game):
    if game['state'] == 1:
        bot.send_message(user_id, texts['remove_unavailable'])
        return save()
    
    if len(game['participants']) <= 1:
        send_all(game['participants'], 'Изи фарм статистики')
        win(game, user_id)
        return

    for i in range(len(game['participants'])):
        if game['participants'][i]['live'] and game['participants'][i]['id'] == user_id:
            game['participants'][i]['live'] = False
            bot.send_message(user_id, texts['dead'])
            previous_index = find_previous_live(game, i)
            next_index = find_next_live(game, i)

            previous_id = game['participants'][previous_index % len(game['participants'])]['id']
            killed_id = game['participants'][i % len(game['participants'])]['id']
            next_id = game['participants'][next_index % len(game['participants'])]['id']

            killer_name = data['nicks'][previous_id]
            killed_name = data['nicks'][killed_id]
            target_name = data['nicks'][next_id]

            data['stats'][previous_id]['kills'] += 1
            data['stats'][killed_id]['deaths'] += 1

            send_all(game['participants'], killer_name + texts['kill'] + killed_name)

            if previous_id == next_id:
                win(game, previous_id)
                return save()
            
            bot.send_message(previous_id, texts['new_target'] + "||" + target_name + "||", parse_mode='MarkdownV2')
            return save()
    bot.send_message(user_id, texts['already_dead'])
    return save()

def send_all(participants, text):
    for player in participants:
        bot.send_message(player['id'], text)

def win(game, winner_id):
    name = data['nicks'][winner_id]
    send_all(game['participants'], name + texts['win'] + name)
    game['state'] = 3
    game['winner'] = name
    data['stats'][winner_id]['wins'] += 1
    data['hosts'].remove(game['host'])

    return save()


@bot.message_handler(commands=['info'])
def info(message):
    if not is_registered(message.chat.id):
        return

    my_message = bot.send_message(message.chat.id, texts['info'])
    bot.register_next_step_handler(my_message, info_name)

def info_name(message):
    user_id = message.chat.id
    game_name = message.text
    for game in data['games']:
        if game['name'] == game_name:
            bot.send_message(user_id, game_info_to_string(game))
            return
    
    bot.send_message(user_id, texts['no_game'])

def game_info_to_string(game):
    info = ''
    info += 'Игра ' + game['name']
    if game['state'] == 1:
        info += ' еще не началась'
    if game['state'] == 2:
        info += ' уже идет'
    if game['state'] == 3:
        info += ' закончилась'
    info += '\n\n'

    shuffled = game['participants'].copy()
    shuffle(shuffled)
    participants = 'Игроки:\n'
    for player in shuffled:
        participants += data['nicks'][player['id']]
        if player['live']:
            participants += ' ГОТОВ УБИВАТЬ'
        else:
            participants += ' ЗАРЕЗАН'
        participants += '\n'

    info += participants
    return info


@bot.message_handler(commands=['stats'])
def stats(message):
    if not is_registered(message.chat.id):
        return

    my_message = bot.send_message(message.chat.id, texts['choose_stats_name'])
    bot.register_next_step_handler(my_message, stats_name)  

def stats_name(message):
    ids = find_id_by_nick(message.text)
    text = stats_to_text(ids)

    if text == '':
        bot.send_message(message.chat.id, texts['no_user_for_stats'])
        return

    bot.send_message(message.chat.id, text)

def stats_to_text(ids):
    text = ''
    for id in ids:
        text += data['nicks'][id] + ':\n'
        text += 'зарезал последнего - ' + str(data['stats'][id]['wins']) + '\n'
        text += 'зарезал - ' + str(data['stats'][id]['kills']) + '\n'
        text += 'был зарезан - ' + str(data['stats'][id]['deaths']) + '\n\n'
    
    return text

def find_id_by_nick(nick):
    ids = []
    for id in data['registered_users']:
        if data['nicks'][id] == nick:
            ids.append(id)

    return ids

@bot.message_handler(commands=['drop_stats'])
def drop_stats(message):
    if not is_registered(message.chat.id):
        return
    
    create_stats(message.chat.id)
    bot.send_message(message.chat.id, texts['deleted'])
    save()

@bot.message_handler(commands=['mailing_all'])
def mailing_all(message):
    if not message.from_user.username in admins:
        return

    my_message = bot.send_message(message.chat.id, 'Что отправить')
    bot.register_next_step_handler(my_message, mailing_all_message)

def mailing_all_message(message):
    for user_id in data['registered_users']:
        bot.send_message(user_id, message.text)

@bot.message_handler(commands=['mailing_game'])
def mailing_game(message):
    if not message.from_user.username in admins:
        return
    
    my_message = bot.send_message(message.chat.id, 'На какую игру разослать?')
    bot.register_next_step_handler(my_message, mailing_game_name)

def find_game_by_name(name):
    for game in data['games']:
        if game['name'] == name:
            return game
    return None

def mailing_game_name(message):
    game = find_game_by_name(message.text)
    if game == None:
        return bot.send_message(message.chat.id, texts['no_game'])
    
    my_message = bot.send_message(message.chat.id, 'Что написать')
    bot.register_next_step_handler(my_message, mailing_game_text, game)

def mailing_game_text(message, game):
    send_all(game['participants'], message.text)

bot.infinity_polling()
