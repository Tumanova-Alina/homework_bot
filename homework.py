import logging
import os
import sys
import time
from http import HTTPStatus

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
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

ERROR_NOTIFIED = False
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

ERROR_MISSING_NAME = 'Отсутствует ключ "homework_name".'
ERROR_MISSING_STATUS = 'Отсутствует ключ "status".'
ERROR_UNKNOWN_STATUS = 'Неизвестный статус работы: {homework_status}'
INFO_STATUS_CHANGE = (
    'Изменился статус проверки работы "{homework_name}". {verdict}'
)
CRITICAL_MISSING_TOKENS = (
    'Отсутствуют обязательные переменные окружения: {missing_tokens}!'
)
DEBUG_MESSAGE_SENT = 'Сообщение успешно отправлено: {message}'
EXCEPTION_MESSAGE = (
    'Сбой при отправке сообщения "{message}" в Telegram: {error}'
)
REQUEST_EXCEPTION_MESSAGE = (
    'Эндпоинт недоступен: {error}. '
    'Параметры запроса: {params}, заголовки: {headers}'
)
STATUS_CODE_ERROR_MESSAGE = (
    'API вернул статус: {status_code}. '
    'Параметры запроса: {params}, заголовки: {headers}'
)
API_RESPONSE_ERROR_MESSAGE = (
    'Ошибка в ответе API: {response_json}. '
    'Параметры запроса: {params}, заголовки: {headers}'
)
API_RESPONSE_TYPE_ERROR = 'Ответ API должен быть словарём, а не {actual_type}.'
API_KEY_ERROR = 'Отсутствуют ожидаемые ключи в ответе API.'
API_HOMEWORKS_TYPE_ERROR = (
    'Неверный формат данных в ответе API: '
    'ожидается список, получен {actual_type}.'
)
API_SUCCESS_LOG = 'Ответ API успешно проверен. Данные корректны.'
EXIT_MESSAGE = 'Программа остановлена из-за отсутствия переменных окружения.'
NO_NEW_HOMEWORK_LOG = 'Отсутствуют новые статусы домашних заданий.'
ERROR_MESSAGE = 'Сбой в работе программы: {error}.'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        critical_message = CRITICAL_MISSING_TOKENS.format(
            missing_tokens=", ".join(missing_tokens)
        )
        logger.critical(critical_message)
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram-чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message,
                         )
        logger.debug(DEBUG_MESSAGE_SENT.format(message=message))
    except Exception as error:
        logger.exception(
            EXCEPTION_MESSAGE.format(message=message, error=error)
        )


def get_api_answer(timestamp):
    """Запрос к API сервиса Практикум Домашка."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        raise RuntimeError(REQUEST_EXCEPTION_MESSAGE.format(
            error=error, params=params, headers=HEADERS))

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(STATUS_CODE_ERROR_MESSAGE.format(
            status_code=response.status_code, params=params, headers=HEADERS))

    response_json = response.json()

    if 'code' in response_json or 'error' in response_json:
        raise RuntimeError(API_RESPONSE_ERROR_MESSAGE.format(
            response_json=response_json, params=params, headers=HEADERS))

    return response_json


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            API_RESPONSE_TYPE_ERROR.format(actual_type=type(response).__name__)
        )
    if 'homeworks' not in response:
        raise KeyError(API_KEY_ERROR)

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError(
            API_HOMEWORKS_TYPE_ERROR.format(
                actual_type=type(homeworks).__name__
            )
        )
    logger.debug(API_SUCCESS_LOG)
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(ERROR_MISSING_NAME)
    if 'status' not in homework:
        raise KeyError(ERROR_MISSING_STATUS)

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        error_message = ERROR_UNKNOWN_STATUS.format(
            homework_status=homework_status)
        raise ValueError(error_message)

    verdict = HOMEWORK_VERDICTS[homework_status]
    info_message = INFO_STATUS_CHANGE.format(
        homework_name=homework_name, verdict=verdict
    )
    return info_message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug(NO_NEW_HOMEWORK_LOG)

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            error_formatted = ERROR_MESSAGE.format(error=error)
            for action in [logger.error, lambda msg: send_message(bot, msg)]:
                action(error_formatted)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.critical(EXIT_MESSAGE)
        sys.exit(0)
