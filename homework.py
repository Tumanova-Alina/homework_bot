import logging
import requests
import time
from telebot import TeleBot, types
import os
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),  # Вывод логов в консоль
        logging.FileHandler('bot.log', encoding='utf-8')  # Вывод логов в файл
    ]
)

# logger = logging.getLogger(__name__)

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
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(
            types.KeyboardButton('/start'),  # Создаём первую кнопку в строке.
        )
        keyboard.row(
            types.KeyboardButton('/check_homework'),
        )
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message,
                         reply_markup=keyboard
                         )
        logging.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Запрос к API сервиса Практикум Домашка."""
    # homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
    # return homework_statuses.json()
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка запроса к эндпоинту API: {error}')
        raise RuntimeError(f'Эндпоинт недоступен: {error}')


def check_response(response):
    """Проверка ответа API на корректность."""
    if 'homeworks' not in response or 'current_date' not in response:
        logging.error(
            '"homeworks" или "current_date" отсутствуют в ответе API.'
        )
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API.')
    if not isinstance(response['homeworks'], list):
        logging.error('Ответ API содержит неверный тип данных: "homeworks" не является списком.')
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

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)     

            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                ERROR_NOTIFIED = False  # Сбрасываем флаг при успешной итерации
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
                ERROR_NOTIFIED = True  # Устанавливаем флаг, чтобы избежать повторных сообщений

        # except Exception as error:
        #     message = f'Сбой в работе программы: {error}'
            ...
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
