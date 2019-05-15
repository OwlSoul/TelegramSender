# TelegramSender

The little Telegram bot, which will receive the message from the socket and broadcast it to all registered users. Requires PostrgeSQL database to work. Mostly used for notifications.

![Telegram Sender](https://raw.githubusercontent.com/OwlSoul/Images/master/TelegramSender/image-01.jpg)

To receive messages, user will need to register with the bot, using the command `/register:SecretWord`. The SecretWord is a password which is set when running the bot. The bot will passively-aggressively ignore any of your interactions except /start, unless he knows you. And by "he knows you" it means that you registered with the right SecretWord.

By default the bot listens on port 16001, the idea that is you send a message there (using netcat, for example), and as soon as you terminate the connection on the socket, the message will be broadcasted via telegram.

## Bot commands
```
/start               - Start interacting with the bot
/register:SecretWord - Say the secret and the bot will register you. Don't forget the SecretWord (/register:SecretWord)
/forget              - Let the bot forget you
/users               - See the chat IDs of other users registered with the bot
```

## Requirements
Bot requires a Python3 and the following libraries:

```
pip3 install psycopg2-binary 
pip3 install python-telegram-bot
```

Also, you'll need to register your own bot and obtain Telegram Bot Token. Pay respects to the [BotFather](https://telegram.me/BotFather) for this. Mind your manners in his presense.

## Preparing the database (PostrgeSQL)

These are commands required to create the user and database with which the bot will work by default:

```
CREATE USER sender_bot WITH ENCRYPTED PASSWORD 'password';

CREATE DATABASE sender_bot;

\c sender_bot;

CREATE TABLE chats (
    chat_id varchar PRIMARY KEY
);

GRANT ALL PRIVILEGES ON SCHEMA public TO sender_bot;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sender_bot;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sender_bot;
GRANT ALL PRIVILEGES ON DATABASE sender_bot TO sender_bot;
```

Change the user, database name and password according to your desires, of course.

## Running the bot

Supply the bot with the token, secret word, host:port (optional) and the database settings. Something like this:

```
sender_bot.p TOKEN --secret SECRETWORD --db_host 127.0.0.1 --db_name sender_bot --db_user sender_bot --db_pass password --verbose 3
```

Bot supports the following CLI arguments:
```
positional arguments:
  token              telegram bot token

optional arguments:
  -h, --help         show this help message and exit
  -v, --version      show version info
  --host HOST        host to listen on, default is 127.0.0.1
  --port PORT        port to listen on, default is 16001
  --secret WORD      secret word to register, default: password
  --db_host DB_HOST  database host, default is: 127.0.0.1
  --db_port DB_PORT  database port, default is: 5432
  --db_name DB_NAME  database name, default is: sender_bot
  --db_user USER     database username, default is: sender_bot
  --db_pass PASS     database password, default is: password
  --verbose VERBOSE  log verbose level, possible values:
                        0 : no debug
                        1 : error messages only
                        2 : errors and warnings
                        3 : errors, warnings and info
                        4 : full debug
                     default is 3

```

## Testing the bot
Now, to test the bot, use netcat. Assuming the bot listens (as by default) on 127.0.0.1:16001:

```
nc 127.0.0.1 16001
```

Type the message, don't forget to press enter after each line and before you finish.
Now, terminate netcat the connection (CTRL+C), and the message will be broadcasted.

## Using the dockerized version of the bot

You can either build the image by yourself:

```
docker build -t "owlsoul/telegram-sender:dev" .
```

Or just use the DockerHub image:

```
docker pull "owlsoul/telegram-sender:dev"
```

Now, use command like this to run the bot inside the docker container. Good thing is that you have a log now, and the bot will also autorestart if it fails.

```
docker run -it -d --restart unless-stopped --name telegram-sender -p 16001:16001 owlsoul/telegram-sender:dev sender_bot.py TOKEN --secret SECRETWORD --db_host 172.17.0.1 --db_name sender_bot --db_user sender_bot --db_pass password --verbose 3
```

## License
The code is distributed under LGPLv3 licence, author do not bear any responsibility for possible problems with usage of this project (but he will be very sad).

## Credits
__Project author:__ [Yury D.](https://github.com/OwlSoul) (TheOwlSoul@gmail.com)
