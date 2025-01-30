import logging
import os
import time
from http import HTTPStatus

import requests
from telebot import TeleBot
from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


def setup_custom_logger(name):
    """Создать и настроить отдельный логгер для модуля."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.hasHandlers():
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        file_handler = logging.FileHandler('bot.log', encoding='utf-8')
        file_handler.setFormatter(formatter)

        logger.addHandler(stream_handler)
        logger.addHandler(file_handler)

    return logger


logger = setup_custom_logger(__name__)

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
    'Эндпоинт {endpoint} недоступен: {error}. '
    'Параметры запроса: {params}, заголовки: {headers}'
)
STATUS_CODE_ERROR_MESSAGE = (
    'API вернул статус: {status_code}. '
    'Параметры запроса: {params}, заголовки: {headers}, эндпоинт: {endpoint}'
)
API_RESPONSE_ERROR_MESSAGE = (
    'Ошибка в ответе API: ключ — {error_key}, значение — {error_value}. '
    'Параметры запроса: {params}, заголовки: {headers}, эндпоинт: {endpoint}'
)
API_RESPONSE_TYPE_ERROR = 'Ответ API должен быть словарём, а не {actual_type}.'
API_RESPONSE_KEY_ERROR = 'Отсутствуют ожидаемые ключи в ответе API.'
API_HOMEWORKS_TYPE_ERROR = (
    'Неверный формат данных в ответе API: '
    'ожидается список, получен {actual_type}.'
)
API_SUCCESS_LOG = 'Ответ API успешно проверен. Данные корректны.'
EXIT_MESSAGE = 'Программа остановлена из-за отсутствия переменных окружения.'
NO_NEW_HOMEWORK_LOG = 'Отсутствуют новые статусы домашних заданий.'
ERROR_MESSAGE = 'Сбой в работе программы: {error}.'
TOKEN_NAMES = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']


def check_tokens():
    """Проверка доступности переменных окружения."""
    missing_tokens = [name for name in TOKEN_NAMES if not globals().get(name)]
    if missing_tokens:
        critical_message = CRITICAL_MISSING_TOKENS.format(
            missing_tokens=missing_tokens
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
    except requests.RequestException as error:
        raise ConnectionError(REQUEST_EXCEPTION_MESSAGE.format(
            error=error, params=params, headers=HEADERS, endpoint=ENDPOINT))

    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(STATUS_CODE_ERROR_MESSAGE.format(
            status_code=response.status_code,
            params=params, headers=HEADERS, endpoint=ENDPOINT)
        )

    response_json = response.json()

    for error_key in ['code', 'error']:
        if error_key in response_json:
            error_value = response_json[error_key]
            raise ConnectionError(API_RESPONSE_ERROR_MESSAGE.format(
                error_key=error_key, error_value=error_value,
                params=params, headers=HEADERS, endpoint=ENDPOINT)
            )

    return response_json


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            API_RESPONSE_TYPE_ERROR.format(actual_type=type(response).__name__)
        )
    if 'homeworks' not in response:
        raise KeyError(API_RESPONSE_KEY_ERROR)

    homeworks = response['homeworks']

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
    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            message_sent = False

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                message_sent = True
            else:
                logger.debug(NO_NEW_HOMEWORK_LOG)

            if message_sent:
                timestamp = response.get('current_date', timestamp)

        except Exception as error:
            error_formatted = ERROR_MESSAGE.format(error=error)
            if error_formatted != last_error_message:
                send_message(bot, error_formatted)
                logger.error(error_formatted)
                last_error_message = error_formatted
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
