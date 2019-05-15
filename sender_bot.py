#!/usr/bin/env python3

"""
Telegram sender bot, it will receive a message on socket and will broadcast it to all subscribers.
Each subscriber needs to register first, using command "/register:SecretWord", the SecretWord
is chosen by the bot owner.

Requires PostgreSQL database to work.
"""

import argparse
import sys
import signal
import logging
import threading
import time
import socket
import socketserver
import psycopg2
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram import __version__ as TELEGRAM_API_VERSION

__author__ = "Yury D."
__credits__ = ["Yury D."]
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = "Yury D."
__email__ = "TheOwlSoul@gmail.com"
__status__ = "Beta"


class MyTCPRequestHandler(socketserver.StreamRequestHandler):
    """
    Handler for TCP request handler.
    """
    def handle(self):
        """
        Request handler. Will process the incoming message and broadcast it via Telegram.
        :return: nothing
        """
        # Oow, that's dirty!
        # Do you think so?
        # Well I better not show you
        # How deploying here is made...
        global application

        # Getting the message
        try:
            logging.info("Received message %s", self.client_address[0])
            msg = self.rfile.read().strip().decode('utf-8')
            logging.info("Message to broadcast: %s", msg)
        except Exception as e:
            logging.error("Error %s", str(e))

        # Broadcasting the message
        application.broadcast(msg)

        logging.info("Handling of message complete!")


class TCPServerThread(threading.Thread):
    """
    TCP Server thread, it will run separately from the main one.
    """
    def __init__(self, app):
        super().__init__()

        self.app = app
    def run(self):
        """
        The 'run' function of TCP Server thread, will create a TCPServer and listen
        until terminated.
        :return: nothing
        """
        logging.info("TCPServer thread started.")
        # Creating TCP server
        tcp_server = socketserver.TCPServer((self.app.host, self.app.port), MyTCPRequestHandler)
        tcp_server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp_server.socket.settimeout(1)

        while self.app.is_running:
            tcp_server.handle_request()

        logging.info("TCPServer thread terminated.")


class Application:
    """
    Main application class.
    """
    # Debug values
    LOG_NONE = 0
    LOG_ERROR = 1
    LOG_WARNING = 2
    LOG_INFO = 3
    LOG_DEBUG = 4

    def __init__(self):
        # While True, the programm will be running
        self.is_running = True

        # Verbosity level
        self.verbose = self.LOG_INFO

        # Host and port to listen on
        self.host = '127.0.0.1'
        self.port = 16001

        # If true, will print users from the database on screen during startup.
        self.print_users_from_db = True

        self.token = ''

        # Secret word to register the user permanently.
        self.secret_word = 'password'

        # Database settings
        self.db_settings = {'db_host': '127.0.0.1',
                            'db_port': 5432,
                            'db_name': 'sender_bot',
                            'db_user': 'sender_bot',
                            'db_pass': 'password'}

        # Chat IDs are stored here
        self.chat_ids = []

        # Telegram updater and dispatcher
        self.updater = None
        self.dispatcher = None

    def stop_polling(self):
        """
        Stop polling.
        :return: nothing
        """
        logging.info("Stopping poller now!")
        self.updater.stop()

    def sigint_handler(self, sig, tim):
        """
                SIGINT handler
                :param sig: signal
                :param tim: time frame
                :return:  nothing
                """
        logging.info("SIGINT received!")
        self.shutdown()

    def sigterm_handler(self, sig, tim):
        """
        SIGTERM handler
        :param sig: signal
        :param tim: time frame
        :return:  nothing
        """
        logging.info("SIGTERM received!")
        self.shutdown()

    @staticmethod
    def load_chat_ids_from_database(db_settings):
        """
        Load chat_ids from the database
        :param db_settings: database settings
        :return: chat_ids, list. Empty if error.
        """
        # Connect
        try:
            conn = psycopg2.connect(dbname=db_settings['db_name'],
                                    host=db_settings['db_host'],
                                    user=db_settings['db_user'],
                                    port=db_settings['db_port'],
                                    password=db_settings['db_pass'])
        except Exception as e:
            logging.error("Exception (load_chat_ids_from_database connect): %s", str(e))
            return []

        # Query
        cur = conn.cursor()
        sql_query = "SELECT chat_id FROM chats"
        try:
            cur.execute(sql_query)
            rows = cur.fetchall()
        except Exception as e:
            logging.error("Exception (load_chat_ids_from_database query): %s", str(e))
            return []

        # Close
        try:
            cur.close()
            conn.close()
        except Exception as e:
            logging.error("Exception (load_chat_ids_from_database close): %s", str(e))
            return []

        # Return
        result = []
        for row in rows:
            result.append(row[0])

        return result

    @staticmethod
    def save_chat_ids_to_database(db_settings, chat_ids):
        """
        Update chat_ids in the database.
        :param db_settings: database settings
        :param chat_ids: chat_ids to be updated, list.
        :return: 0 if OK, error code if not
        """
        # Connect
        try:
            conn = psycopg2.connect(dbname=db_settings['db_name'],
                                    host=db_settings['db_host'],
                                    user=db_settings['db_user'],
                                    port=db_settings['db_port'],
                                    password=db_settings['db_pass'])
        except Exception as e:
            logging.error("Exception (save_chat_ids_to_database connect) %s:", str(e))
            return 1

        # Query
        cur = conn.cursor()
        sql_query = "INSERT INTO chats(chat_id) VALUES"

        for i in range(0, len(chat_ids)-1):
            sql_query += "('" + str(chat_ids[i]) + "'),"
        sql_query += "('" + str(chat_ids[-1]) + "')"

        sql_query += " ON CONFLICT DO NOTHING"

        try:
            cur.execute(sql_query)
        except Exception as e:
            logging.error("Exception (save_chat_ids_to_database query): %s", str(e))
            return 2

        # Close
        try:
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logging.error("Exception (save_chat_ids_to_database close): %s", str(e))
            return 3

        # Return
        return 0

    @staticmethod
    def delete_chat_id_from_database(db_settings, chat_id):
        """
        Delete chat_id from the database.
        :param db_settings: database settings
        :param chat_id: chat_id to delete
        :return: 0 if OK, error code if not
        """
        # Connect
        try:
            conn = psycopg2.connect(dbname=db_settings['db_name'],
                                    host=db_settings['db_host'],
                                    user=db_settings['db_user'],
                                    port=db_settings['db_port'],
                                    password=db_settings['db_pass'])
        except Exception as e:
            logging.error("Exception (delete_chat_id_from_database connect): %s", str(e))
            return 1

        # Query
        cur = conn.cursor()
        sql_query = "DELETE FROM chats WHERE chat_id='"+chat_id+"'"

        try:
            cur.execute(sql_query)
        except Exception as e:
            logging.error("Exception (delete_chat_id_from_database query): %s", str(e))
            return 2

        # Close
        try:
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logging.error("Exception (delete_chat_id_from_database close): %s", str(e))
            return 3

        # Return
        return 0

    def shutdown(self):
        """
        Initiate shutdown. This will stop the bot.
        :return: nothing
        """
        self.broadcast("The bot is terminated!")
        self.updater.stop()
        self.updater.is_idle = False

    @staticmethod
    def start(bot, update):
        """
        Process /start command.
        Just greet the user, hinting him to use the SecretWord.
        :param bot: the telegram bot
        :param update: telegram update message
        :return: nothing
        """
        logging.info("Command: /start from %s", str(update.message.chat_id))

        logging.info("Recorded user ID: %s", str(update.message.chat_id))
        bot.send_message(chat_id=update.message.chat_id,
                         text="Just say the word...")

    def register(self, bot, update):
        """
        Process the /register:SecretWord command.
        If a user used the right secret word, he will become registered.
        :param bot: the telegram bot
        :param update: telegram update message
        :return: nothing
        """
        logging.info("Command: /register from %s", str(update.message.chat_id))

        self.chat_ids.append(update.message.chat_id)
        result = self.save_chat_ids_to_database(self.db_settings, self.chat_ids)
        if result != 0:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Failed to add you to the broadcast list. Error code: " +
                             str(result))
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text="You are added to the broadcast list.")

    def forget(self, bot, update):
        """
        Process the /forget command.
        Will unregister the user who used this command.
        :param bot: the telegram bot
        :param update: telegram update message
        :return: nothing
        """
        # Silently ignoring if the user is not registered
        if not str(update.message.chat_id) in self.chat_ids:
            return

        logging.info("Command: /forget from %s", str(update.message.chat_id))

        chat_id = str(update.message.chat_id)
        self.chat_ids.remove(chat_id)

        result = self.delete_chat_id_from_database(self.db_settings, chat_id)

        if result != 0:
            bot.send_message(chat_id=update.message.chat_id,
                             text="Failed to delete you from the broadcast list. Error code: " +
                             str(result))
        else:
            bot.send_message(chat_id=update.message.chat_id,
                             text="You are deleted from the broadcast list.")

    def users(self, bot, update):
        """
        Process the /users command.
        It will print the chat_ids of currently registered users.
        :param bot: the telegram bot
        :param update: telegram update message
        :return: nothing
        """
        # Silently ignoring if the user is not registered
        if not str(update.message.chat_id) in self.chat_ids:
            return

        logging.info("Command: /users from %s", str(update.message.chat_id))

        send_string = "Current saved subscribers of the channel:\n"
        subscribers = self.load_chat_ids_from_database(self.db_settings)

        for line in subscribers:
            send_string += " " + str(line) + "\n"

        bot.send_message(chat_id=update.message.chat_id,
                         text=send_string)

    def broadcast(self, broadcast_text):
        """
        Broadcast the message via TELEGRAM.
        Will do nothing is broadcast_text is empty.
        :param broadcast_text: message to be broadcasted
        :return: nothing
        """
        if not broadcast_text:
            logging.warning("Broadcast message is empty")
            return

        for line in self.chat_ids:
            self.updater.bot.send_message(chat_id=line,
                                          text=broadcast_text)

    def parse_arguments(self):
        """
        Parse CLI argunemts.
        :return: nothing
        """
        #pylint:disable=C0301
        parser = argparse.ArgumentParser(description="This bot will listen on specified port and will"
                                                     "broadcast all messages it receives on it to all"
                                                     "users who are registered. Requires PostgreSQL "
                                                     "database."
                                                     ""
                                                     "And you need a secret word to register, by the way.",
                                         formatter_class=argparse.RawTextHelpFormatter)

        parser.add_argument("-v", "--version", action="store_true", default=False,
                            help="show version info")
        parser.add_argument("token", default="", nargs='?',
                            help="telegram bot token")
        parser.add_argument("--host", metavar="HOST", default=self.host,
                            help="host to listen on, default is " + str(self.host))
        parser.add_argument("--port", metavar="PORT", default=self.port,
                            help="port to listen on, default is " + str(self.port))
        parser.add_argument("--secret", metavar="WORD", default=self.secret_word,
                            help="secret word to register, default: " + str(self.secret_word))
        parser.add_argument("--db_host", metavar="DB_HOST", default=self.db_settings['db_host'],
                            help="database host, default is: " + str(self.db_settings['db_host']))
        parser.add_argument("--db_port", metavar="DB_PORT", default=self.db_settings['db_port'],
                            help="database port, default is: " + str(self.db_settings['db_port']))
        parser.add_argument("--db_name", metavar="DB_NAME", default=self.db_settings['db_name'],
                            help="database name, default is: " + str(self.db_settings['db_name']))
        parser.add_argument("--db_user", metavar="USER", default=self.db_settings['db_user'],
                            help="database username, default is: " + str(self.db_settings['db_user']))
        parser.add_argument("--db_pass", metavar="PASS", default=self.db_settings['db_pass'],
                            help="database password, default is: " + str(self.db_settings['db_pass']))
        parser.add_argument("--verbose", default=self.verbose,
                            help=
                            "log verbose level, possible values:\r" +
                            "   0 : no debug\n" +
                            "   1 : error messages only\n" +
                            "   2 : errors and warnings\n" +
                            "   3 : errors, warnings and info\n" +
                            "   4 : full debug\n" +
                            "default is " + str(self.verbose))
        #pylint:enable=C0301

        args = parser.parse_args()

        if args.version:
            print(__version__)
            sys.exit(0)

        if args.token:
            self.token = args.token
        else:
            print("No source URL, station id or filename provided!")
            sys.exit(0)

        self.secret_word = args.secret
        self.host = args.host
        self.port = int(args.port)
        self.db_settings['db_host'] = args.db_host
        self.db_settings['db_port'] = int(args.db_port)
        self.db_settings['db_name'] = args.db_name
        self.db_settings['db_user'] = args.db_user
        self.db_settings['db_pass'] = args.db_pass

        self.verbose = int(args.verbose)

        # Set logging level

        if self.verbose == self.LOG_ERROR:
            logging.basicConfig(format='[%(asctime)s] %(name)s : %(levelname)s : %(message)s',
                                level=logging.ERROR)
        elif self.verbose == self.LOG_WARNING:
            logging.basicConfig(format='[%(asctime)s] %(name)s : %(levelname)s : %(message)s',
                                level=logging.WARNING)
        elif self.verbose == self.LOG_INFO:
            logging.basicConfig(format='[%(asctime)s] %(name)s : %(levelname)s : %(message)s',
                                level=logging.INFO)
        elif self.verbose == self.LOG_DEBUG:
            logging.basicConfig(format='[%(asctime)s] %(name)s : %(levelname)s : %(message)s',
                                level=logging.DEBUG)
        elif self.verbose == self.LOG_NONE:
            logging.basicConfig(format='[%(asctime)s] %(name)s : %(levelname)s : %(message)s',
                                level=logging.NOTSET)
        else:
            logging.basicConfig(format='[%(asctime)s] %(name)s : %(levelname)s : %(message)s',
                                level=logging.ERROR)

        # Printing values on screen for debug
        logging.debug("Token  : %s ", str(self.token))
        logging.debug("Host   : %s ", str(self.host))
        logging.debug("Port   : %s ", str(self.port))
        logging.debug("Secret : %s ", str(self.secret_word))
        logging.debug("DB_HOST: %s", str(self.db_settings['db_host']))
        logging.debug("DB_PORT: %s", str(self.db_settings['db_port']))
        logging.debug("DB_NAME: %s", str(self.db_settings['db_name']))
        logging.debug("DB_USER: %s", str(self.db_settings['db_user']))
        logging.debug("DB_PASS: %s", str(self.db_settings['db_pass']))

    def run(self):
        """
        Run the main application
        :return: nothing
        """
        signal.signal(signal.SIGINT, self.sigint_handler)
        signal.signal(signal.SIGTERM, self.sigterm_handler)

        self.parse_arguments()
        logging.info("API library version: %s", str(TELEGRAM_API_VERSION))

        # Loading Chat IDs from Database
        logging.info("Loading chat ID's from Database...")
        self.chat_ids = self.load_chat_ids_from_database(self.db_settings)
        if self.print_users_from_db:
            print()
            print("Users:")
            for chat_id in self.chat_ids:
                print(" " + str(chat_id))
            print()

        # Setting the bot up
        self.updater = Updater(token=self.token)
        self.dispatcher = self.updater.dispatcher

        # Command: /start
        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        # Command: /forget
        forget_handler = CommandHandler('forget', self.forget)
        self.dispatcher.add_handler(forget_handler)

        # Command: /register
        register_handler = CommandHandler('register:' + self.secret_word, self.register)
        self.dispatcher.add_handler(register_handler)

        # Command: /users
        users_handler = CommandHandler('users', self.users)
        self.dispatcher.add_handler(users_handler)

        # Broadcasting the message that bot is up and running
        try:
            logging.info("Broadcasting the message now")
            if self.updater:
                self.broadcast("Bot is up and running!")
        except Exception as e:
            logging.error("Failed to broadcast a message!")
            logging.error(str(e))

        # Start TCP Server
        tcp_server_thread = TCPServerThread(self)
        tcp_server_thread.start()

        # Start polling
        logging.info("Start polling")
        self.updater.start_polling(timeout=500)
        logging.info("Polling started, write 'q' to exit.")
        while self.is_running:
            cmd = input().strip()
            if cmd == 'q':
                logging.info("Terminating the program!")
                self.shutdown()
                self.is_running = False
            time.sleep(0.01)

        tcp_server_thread.join()

        logging.info("Application terminated!")

if __name__ == '__main__':
    application = Application()
    application.run()
    sys.exit(0)
