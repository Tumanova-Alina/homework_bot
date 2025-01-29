import logging
import os
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
    ]
)


ERROR_NOTIFIED = False
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if not all(tokens):
        logging.critical('Отсутствуют обязательные переменные окружения!')
    return all(tokens)


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message,
                         )
        logging.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Запрос к API сервиса Практикум Домашка."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != 200:
            raise RuntimeError(f'API вернул статус: {response.status_code}')
        return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка запроса к эндпоинту API: {error}')
        raise RuntimeError(f'Эндпоинт недоступен: {error}')


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём')

    if 'homeworks' not in response or 'current_date' not in response:
        logging.error(
            '"homeworks" или "current_date" отсутствуют в ответе API.'
        )
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API.')
    if not isinstance(response['homeworks'], list):
        logging.error(
            '''Ответ API содержит неверный
            тип данных: "homeworks" не является списком.''')
        raise TypeError('Неверный формат данных в ответе API.')
    logging.debug('Ответ API успешно проверен. Данные корректны.')
    return response['homeworks']


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework or 'status' not in homework:
        logging.error(
            'Отсутствуют ключи "homework_name" или "status".'
        )
        raise KeyError('Отсутствуют ключи "homework_name" или "status".')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        logging.error(f'Неизвестный статус работы: {homework_status}')
        raise ValueError(f'Неизвестный статус работы: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info(
        f'Изменился статус проверки работы: "{homework_name}". {verdict}'
    )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    global ERROR_NOTIFIED
    if not check_tokens():
        exit('Программа остановлена из-за отсутствия переменных окружения.')

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - 20 * 24 * 3600

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
                    ERROR_NOTIFIED = False
            else:
                logging.debug('Отсутствуют новые статусы домашних заданий.')

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')

            if not ERROR_NOTIFIED:
                try:
                    send_message(bot, f'Сбой в работе программы: {error}')
                except Exception as tg_error:
                    logging.error(
                        f'Не удалось отправить сообщение об ошибке: {tg_error}'
                    )
                ERROR_NOTIFIED = True
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
