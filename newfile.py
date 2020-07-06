import time
import config
import sqlite3
import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ReplyKeyboardMarkup

__connection = None


def get_connection():
	global __connection
	if __connection is None:
		__connection = sqlite3.connect('anketa.db', check_same_thread = False)
	return __connection


def init_db():
	conn = get_connection()
	c = conn.cursor()
	c.execute(''' CREATE TABLE IF NOT EXISTS user_message(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, time	INTEGER NOT NULL, text	TEXT NOT NULL, status	TEXT)''')
	c.execute(''' CREATE TABLE IF NOT EXISTS users(id	INTEGER PRIMARY KEY NOT NULL,invited_by_id INTEGER NOT NULL, reffed INTEGER NOT NULL, balance INTEGER NOT NULL, wallet	TEXT, vip_until INTEGER NOT NULL, subscr BOOLEAN NOT NULL, has_free INTEGER NOT NULL, id_free_sig INTEGER,agreed_bool INTEGER NOT NULL, free_sigs INTEGER NOT NULL )''')
	c.execute(''' CREATE TABLE IF NOT EXISTS transactions(hash	TEXT NOT NULL)''')
	conn.commit()


def add_message(time, text):
	conn = get_connection()
	cs = conn.cursor()
	cs.execute("INSERT INTO user_message(time, text) VALUES({0}, '{1}')".format(time, text))
	conn.commit()


def send_verdict_to_vips(id, verdict):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT text FROM user_message WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	if verdict == "✅":
		message = '✅'.format(h)
	else:
		message = '➖'.format(h)
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT id FROM users WHERE (subscr = 1 AND vip_until > {0}) OR id_free_sig = {1} OR free_sigs>0'.format(time.time(), id - 1))
	h = c.fetchall()
	c.execute('SELECT COUNT(*) FROM user_message')
	cnt = c.fetchall()[0][0] - 1
	for user in h:
		if get_free_type(user[0]) == 1:
			increase_free_type(user[0])
			set_free_sig(user[0], cnt)
		bot.sendMessage(user[0], message)
	bot.sendMessage(config.CHANNEL_NAME, message)


def set_verdict(id, verdict):
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE user_message SET status = '{0}' WHERE id = {1}".format(verdict, id))
	conn.commit()


def is_registrated(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT COUNT(*) FROM users WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	return h > 0


def register(message):

	try:
		inviter = int(message.text[7:])
	except:
		inviter = 0
	conn = get_connection()
	c = conn.cursor()
	c.execute(f"INSERT INTO users(id, balance, vip_until, subscr, has_free,reffed,invited_by_id,agreed_bool,free_sigs) VALUES({message.chat_id}, 0, 0, 1, 0,0,{inviter},0,0)")
	conn.commit()
	c.execute("")
	return inviter

def is_with_wallet(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT wallet FROM users WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	return h is not None


def get_balance(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT balance FROM users WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	return h


def get_wallet(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT wallet FROM users WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	return h


def have_this_wallet(wallet):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT COUNT(*) FROM users WHERE wallet = "{0}"'.format(wallet))
	h = c.fetchall()[0][0]
	return h > 0


def top_up(chat_id):
	global bot

	if is_with_wallet(chat_id):
		markup = ReplyKeyboardMarkup([["Обновить баланс", "Меню"]], resize_keyboard=True)
		bot.sendMessage(chat_id, 'Ваш привязанный кошелек: {0}. (Редактировать "wallet x")\nВаш баланс {1} $'.format(get_wallet(chat_id), get_balance(chat_id)), reply_markup=markup)
	else:
		markup = ReplyKeyboardMarkup([["Меню"]], resize_keyboard=True)
		bot.sendMessage(chat_id, 'Чтобы пополнить кошелек, нужно сначала ввести свой.\nДля этого нужно ввести "wallet x", где x - номер Вашего кошелька', reply_markup=markup)


def tie(chat_id, message):
	global bot

	wal = message.split(" ")[1]
	if have_this_wallet(wal):
		bot.sendMessage(chat_id, "Кто-то уже использует такой кошелек")
		return
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE users SET wallet = '{0}' WHERE id = {1}".format(wal, chat_id))
	conn.commit()


def is_used_hash(hash):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT COUNT(*) FROM transactions WHERE hash = "{0}"'.format(hash))
	h = c.fetchall()[0][0]
	return h > 0


def add_hash(hash):
	conn = get_connection()
	c = conn.cursor()
	c.execute('INSERT INTO transactions(hash) VALUES("{0}")'.format(hash))
	conn.commit()


def set_balance(id, balance):
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE users SET balance = '{0}' WHERE id = {1}".format(balance, id))
	conn.commit()


def get_rate():
	req = requests.get("https://blockchain.info/ticker").json()["USD"]["15m"]
	return req


def update_balance(id):
	wallet = get_wallet(id)
	url = "https://api.blockcypher.com/v1/btc/main/addrs/" + config.ADMIN_ADDRESS
	req = requests.get(url)
	trans = req.json()["txrefs"]
	addsum = 0
	for tran in trans:
		value = tran["value"]
		hash = tran["tx_hash"]
		date = tran["confirmed"]
		date = time.mktime(time.strptime(date, '%Y-%m-%dT%H:%M:%SZ'))
		if date > time.time() - 60 * 60:
			continue
		if is_used_hash(hash):
			continue
		url_wal = "https://api.blockcypher.com/v1/btc/main/txs/" + hash
		ans = requests.get(url_wal).json()["inputs"][0]["addresses"]
		if len(ans) != 1:
			continue
		if ans[0] == config.ADMIN_ADDRESS:
			continue
		wal = ans[0]
		if wal != wallet:
			continue
		addsum += value
		add_hash(hash)
	now = get_balance(id) + addsum / (10 ** 8) * get_rate()
	set_balance(id, now)


def get_vip(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT vip_until FROM users WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	return h


def add_vip(id, days):
	vip_until = max(time.time(), get_vip(id))
	vip_until += days * 24 * 60 * 60
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE users SET vip_until = {0} WHERE id = {1}".format(vip_until, id))
	conn.commit()


def get_free_type(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT has_free FROM users WHERE id = {0}'.format(id))
	h = c.fetchall()[0][0]
	return h


def increase_free_type(id):
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE users SET has_free = {0} WHERE id = {1}".format(get_free_type(id) + 1, id))
	conn.commit()


def set_free_sig(id, nom):
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE users SET id_free_sig = {0} WHERE id = {1}".format(nom, id))
	conn.commit()


def send_signal_to_vips(sig):
	print("sent")
	message = "Сигнал ! \n{0}".format(sig)
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT id FROM users WHERE (subscr = 1 AND vip_until > {0}) OR has_free = 1 OR free_sigs>0'.format(time.time()))
	h = c.fetchall()
	c.execute('SELECT COUNT(*) FROM user_message')
	cnt = c.fetchall()[0][0] - 1
	for user in h:

		print(user[0])
		c.execute(f"SELECT free_sigs FROM users WHERE id is {user[0]}")
		free_sigs = int(c.fetchall()[0][0])
		#print("free_sigs:"+free_sigs)

		if get_free_type(user[0]) == 1 or free_sigs>0:
			if free_sigs>0:
				c.execute(f"UPDATE users SET free_sigs=free_sigs-1 WHERE id is {user[0]}")
			else:
				increase_free_type(user[0])
				set_free_sig(user[0], cnt)
		bot.sendMessage(user[0], message)
	bot.sendMessage(config.CHANNEL_NAME, message)


def set_subscr(id, x):
	conn = get_connection()
	c = conn.cursor()
	c.execute("UPDATE users SET subscr = {0} WHERE id = {1}".format(x, id))
	conn.commit()


def main_menu(chat_id):
	global bot

	markup = ReplyKeyboardMarkup([["✅ Получить Сигнал", "📈 Статистика Сигналов"],
								 ["💰 Баланс", "👥 Рефералы" ],
								 ["✌️ О нас", "☎️Поддержка"]],resize_keyboard=True)

	bot.sendMessage(chat_id, 'Main Menu', reply_markup=markup)


def get_signal_menu(chat_id):
	global bot

	markup = ReplyKeyboardMarkup([["🎁  Бесплатный сигнал "], ["📍Включить подачу VIP сигналов"],
									["📍Выключить подачу VIP сигналов"], ["Меню"]], resize_keyboard=True)

	bot.sendMessage(chat_id, 'В этом разделе вы сможете получить 1 бесплатный сигнал.\n Для того что бы вы могли \
	получать сигналы без ограничений, вам нужно оплатить VIP подписку на сигналы в разделе  «💰 Баланс»\nТакже вы \
	сможете получить бесплатные сигналы приводя своих друзей в бота по реферальной ссылке, для этого перейдите в \
	раздел «👥 Рефералы».', reply_markup=markup)


def balance_menu(chat_id):
	global bot

	markup = ReplyKeyboardMarkup([["😎 Купить VIP статус", "💳 Пополнить баланс", "Меню"]], resize_keyboard=True)
	bot.sendMessage(chat_id, 'Ваш баланс ' + str(get_balance(chat_id)) + '$', reply_markup=markup)



def ref(chat_id):
	global bot

	bot.sendMessage(chat_id, 'Ваша реферальная ссылка - ' + "t.me/RichTraders_bot?start=" + str(chat_id))


def buy_status(chat_id):
	global bot

	markup = ReplyKeyboardMarkup([["1 неделя VIP", "1 месяц VIP", "Меню"]], resize_keyboard=True)
	bot.sendMessage(chat_id, '😎 Купить VIP статус\n 1 неделя VIP - 25$\n 1месяц VIP - 70$', reply_markup=markup)


def vip7(chat_id):
	global bot

	balance = get_balance(chat_id)
	if balance < 25:
		bot.sendMessage(chat_id, "У вас недостаточно средств.")
	elif balance >= 25:
		balance -= 25
		set_balance(chat_id, balance)
		add_vip(chat_id, 7)
		bot.sendMessage(chat_id, "Успешно приобретен VIP статус на 7 дней.\nVIP действует до {0}".format(time.ctime(get_vip(chat_id))))
		main_menu(chat_id)
		conn = get_connection()
		cs = conn.cursor()
		cs.execute(f"SELECT invited_by_id FROM users WHERE id is {chat_id}")
		inviter_id = cs.fetchall()[0][0]
		add_vip(inviter_id,1)
		bot.sendMessage(inviter_id,"Один из приглашенных вами пользователей купил vip подписку. Вам начислен один день сигналов.")
def vip30(chat_id):
	global bot

	balance = get_balance(chat_id)
	if balance < 70:
		bot.sendMessage(chat_id, "У вас недостаточно средств.")
	elif balance >= 70:
		balance = balance - 70
		set_balance(chat_id, balance)
		add_vip(chat_id, 30)
		bot.sendMessage(chat_id, "Успешно приобретен VIP статус на 30 дней.\nVIP действует до {0}".format(time.ctime(get_vip(chat_id))))
		conn = get_connection()
		cs = conn.cursor()
		cs.execute(f"SELECT invited_by_id FROM users WHERE id is {chat_id}")
		inviter_id = cs.fetchall()[0][0]
		add_vip(inviter_id, 1)
		bot.sendMessage(inviter_id,
						"Один из приглашенных вами пользователей купил vip подписку. Вам начислен один день сигналов.")

def stat_menu(chat_id):
	global bot

	signal_week = []
	signal_week_stat = []
	signal_moun = []
	signal_moun_stat = []
	week_try = 0
	week_fal = 0
	moun_try = 0
	moun_fal = 0
	i = 0
	conn = get_connection()
	c = conn.cursor()
	c.execute('''SELECT time FROM user_message''')
	vall = c.fetchall()
	for valy in vall:
		val = valy[0]
		if time.time() - val < 30 * 24 * 60 * 60:
			c.execute("SELECT text, status FROM user_message WHERE time = {0}".format(val))
			query = c.fetchall()
			txt = query[0][0]
			stat = query[0][1]
			if time.time() - val < 7 * 24 * 60 * 60:
				signal_week.append(txt)
				signal_week_stat.append(stat)
			signal_moun.append(txt)
			signal_moun_stat.append(stat)
		i += 1
	for sig in signal_week_stat:
		if sig == '✅':
			moun_try += 1
		else:
			week_fal += 1
	for sig in signal_moun_stat:
		if sig == '✅':
			week_try += 1
		else:
			moun_fal += 1
	bot.sendMessage(chat_id, 'В данном меню вы можете ознакомиться с результатами наших сигналов\n\n За неделю:\n ✅ ' +str( week_try) + '\n ➖ ' + str(week_fal) + '\n\n За месяц:\n ✅ ' + str(moun_try) + '\n ➖ ' + str(moun_fal))


def sett_menu(chat_id):
	global bot

	bot.sendMessage(chat_id, 'Пожалуйста относитесь с уважением при разговоре с тех.поддержкой!')
	bot.sendMessage(chat_id, 'https://t.me/joinchat/IIs3yh066I6Q65TTpF9G7A')


def start(bott, update):
	global bot

	if not is_registrated(update.message.chat_id):
		reffed = register(update.message)
	if reffed>0:
		bot.sendMessage(update.message.chat_id,"Подтвердите, что вы человек, нажав на эту кнопку:",reply_markup=ReplyKeyboardMarkup([["ЖМЯК"]], resize_keyboard=True))

	else:
		bot.sendMessage(update.message.chat_id, 'Приветствую тебя, уважаемый пользователь!\n\n Жми на ✅Получить Сигнал», \
		чтобы на основе нашего торгового бота, платформа выдала тебе уже готовый сигнал. На основе точных математических\
		вычислений наша нейронная сеть способна вычислить максимально точный исход без ошибок!\n\n «✌️О наc» -\
		 Тут вы сможете ближе ознакомиться с нашим проектом, узнать алгоритм работы и посмотреть отзывы наших клиентов\n\n \
		 «📈Статистика Сигналов» - это там вы увидите статистику по последним сигналам\n\n «💰Баланс» - Мониторинг вашего \
		 баланса с помощь которого вы сможете покупать VIP сигналы\n\n «👥Рефералы» - В данном разделе вы сможете заработать\
		  на VIP сигналы приглашая своих друзей\n\n В случае если Вы не разобрались с системой или же наша платформа не \
		  отправила Вам точный сигнал, Вы всегда можете обратиться в нашу Тех. поддержку!')
		main_menu(update.message.chat_id)


def sigh(bott, update):
	global bot

	message = update.message.text
	chat_id = update.message.chat_id
	markup = ReplyKeyboardMarkup([["Меню"]], resize_keyboard=True)

	if not is_registrated(chat_id):
		register(chat_id)
	if message == 'ЖМЯК':

		bot.sendMessage(update.message.chat_id, 'Приветствую тебя, уважаемый пользователь!\n\n Жми на ✅Получить Сигнал», \
				чтобы на основе нашего торгового бота, платформа выдала тебе уже готовый сигнал. На основе точных математических\
				вычислений наша нейронная сеть способна вычислить максимально точный исход без ошибок!\n\n «✌️О наc» -\
				 Тут вы сможете ближе ознакомиться с нашим проектом, узнать алгоритм работы и посмотреть отзывы наших клиентов\n\n \
				 «📈Статистика Сигналов» - это там вы увидите статистику по последним сигналам\n\n «💰Баланс» - Мониторинг вашего \
				 баланса с помощь которого вы сможете покупать VIP сигналы\n\n «👥Рефералы» - В данном разделе вы сможете заработать\
				  на VIP сигналы приглашая своих друзей\n\n В случае если Вы не разобрались с системой или же наша платформа не \
				  отправила Вам точный сигнал, Вы всегда можете обратиться в нашу Тех. поддержку!')
		main_menu(update.message.chat_id)
		conn = get_connection()
		cs = conn.cursor()

		cs.execute(f"SELECT agreed_bool FROM users WHERE id is {update.message.chat_id}")
		agreed = cs.fetchall()[0][0]

		if agreed>0:
			bot.sendMessage(update.message.chat_id,"Вы уже нажимали на кнопку, больше не надо.")
		else:
			cs.execute(f"SELECT invited_by_id FROM users WHERE id is {update.message.chat_id}")
			inviter_id = cs.fetchall()[0][0]
			cs.execute(f"UPDATE users SET reffed = reffed + 1 WHERE id IS {inviter_id}")
			cs.execute(f"SELECT reffed FROM users WHERE id is {inviter_id}")
			total_refs = cs.fetchall()[0][0]
			bot.sendMessage(inviter_id,f"Пришел новый клиент по вашей реферальной ссылке. Всего их у вас {total_refs}")

			cs.execute(f"UPDATE users SET agreed_bool = 1 WHERE id IS {update.message.chat_id}")

			if total_refs>=2:
				bot.sendMessage(inviter_id,f"Вам было выдано три бесплатных сигнала за приглашенных вами пользователей.")

				cs.execute(f"UPDATE users SET free_sigs = free_sigs+3 WHERE id IS {inviter_id}")
				cs.execute(f"UPDATE users SET reffed = reffed-2 WHERE  id IS {inviter_id}")

	if message == '✅ Получить Сигнал':
		get_signal_menu(chat_id)

		conn = get_connection()
		cs = conn.cursor()
		cs.execute(f"SELECT free_sigs FROM users WHERE id is {update.message.chat_id}")
		free_signals = cs.fetchall()[0][0]
		print("#")

		vip_days = (get_vip(chat_id)-time.time())
		if vip_days<0:
			vip_days=0
		seconds = vip_days
		seconds_in_day = 60 * 60 * 24
		seconds_in_hour = 60 * 60
		seconds_in_minute = 60
		days = seconds // seconds_in_day
		hours = (seconds - (days * seconds_in_day)) // seconds_in_hour
		minutes = (seconds - (days * seconds_in_day) - (hours * seconds_in_hour)) // seconds_in_minute
		bot.sendMessage(update.message.chat_id,f"Ваш Vip доступ - {int(days)} дней {int(hours)} часов {int(minutes)} минут.\nДоступно бесплатных сигналов - {free_signals}")
	elif message == '🎁  Бесплатный сигнал':
		if get_free_type(chat_id) == 0:
			increase_free_type(chat_id)
			bot.sendMessage(chat_id, 'Ожидайте, в течение дня вам прийдет бесплатный сигнал', reply_markup=markup)
		else:
			bot.sendMessage(chat_id, 'Вы уже использовали эту функцию', reply_markup=markup)

	elif message == '📍Включить подачу VIP сигналов':
		set_subscr(chat_id, 1)
		bot.sendMessage(chat_id, 'Подача VIP сигналов включены')
	elif message == '📍Выключить подачу VIP сигналов':
		set_subscr(chat_id, 0)
		bot.sendMessage(chat_id, 'Подача VIP сигналов отключена')
	elif message == '💳 Пополнить баланс':
		top_up(chat_id)
	elif len(message) > 7 and message[:6] == "wallet":
		tie(chat_id, message)
		top_up(chat_id)
	elif message == 'Обновить баланс':
		update_balance(chat_id)
		top_up(chat_id)
	elif message == 'all':
		if chat_id == config.ADMIN_ID:
			conn = get_connection()
			c = conn.cursor()
			c.execute("SELECT id, text, status FROM user_message")
			values = c.fetchall()
			msg = ""
			for value in values:
				msg += str(value[0]) + '. ' + value[1] + ' - ' + ('-' if value[2] is None else value[2]) + '\n'
			bot.sendMessage(chat_id, msg)
			bot.sendMessage(chat_id, 'Для того, чтобы изменить статус сигнала chng номер и 0/1')
	elif message == '💰 Баланс':
		balance_menu(chat_id)
	elif message == '😎 Купить VIP статус':
		buy_status(chat_id)
	elif message == '📈 Статистика Сигналов':
		stat_menu(chat_id)
	elif message == 'Меню':
		main_menu(chat_id)
	elif message =='☎️Поддержка':
		sett_menu(chat_id)
	elif message == '👥 Рефералы':
		ref(chat_id)
	elif message == "1 неделя VIP":
		vip7(chat_id)
	elif message == "1 месяц VIP":
		vip30(chat_id)
	elif len(message) > 4 and message[:3] == "VIP":
		if chat_id == config.ADMIN_ID:
			sig = message[4:]
			tm = time.time()
			add_message(tm, sig)
			bot.sendMessage(chat_id,  'Сигнал успешно создан')
			send_signal_to_vips(sig)
	elif len(message) > 5 and message[:4] == "chng":
		if chat_id == config.ADMIN_ID:
			nom = message.split(" ")[1]
			verd = ('➖' if message.split(" ")[2] == "0" else '✅')
			set_verdict(nom, verd)
			bot.sendMessage(chat_id,  'Вердикт сигнала изменен')
			send_verdict_to_vips(nom, verd)


def updated(bott, update):
	text = update.edited_message.text
	date = update.edited_message.date
	date = time.mktime(date.timetuple()) + 60 * 60 * config.GMT_HOURS
	if text[:3] != "VIP":
		return
	conn = get_connection()
	c = conn.cursor()
	c.execute('SELECT time FROM user_message')
	h = c.fetchall()
	i = 1
	for each in h:
		if abs(round(each[0]) - date) < config.MAX_DELAY:
			id = i
			break
		i += 1
	if text[-1] == "✅":
		set_verdict(id, "✅")
		send_verdict_to_vips(id, "✅")
		bot.sendMessage(config.ADMIN_ID, 'Вердикт сигнала #' + str(id) + ' был изменен (✅)')
	elif text[-1] == "➖":
		set_verdict(id, "➖")
		send_verdict_to_vips(id, "➖")
		bot.sendMessage(config.ADMIN_ID, 'Вердикт сигнала #' + str(id) + ' был изменен (➖)')


init_db()
updater = Updater(config.TOKEN, use_context=False)
dp = updater.dispatcher
bot = updater.bot
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.update.edited_message, updated))
dp.add_handler(MessageHandler(Filters.text, sigh))
updater.start_polling()
