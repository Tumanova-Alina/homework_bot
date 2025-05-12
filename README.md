# homework_bot

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![dotenv](https://img.shields.io/badge/dotenv-1.0.0-brightgreen.svg)
![pyTelegramBotAPI](https://img.shields.io/badge/pyTelegramBotAPI-4.12.0-blue)
![pytest](https://img.shields.io/badge/pytest-7.4.4-yellow)

## Описание 
Бот-ассистент обращается к API сервису Практикум.Домашка и узнаёт статус домашней работы: взята ли домашняя работа в ревью, проверена ли она, а если проверена — то принял её ревьюер или вернул на доработку.

## Запуск проекта в dev-режиме

1. Клонировать репозиторий:

    ```bash
    https://github.com/Tumanova-Alina/homework_bot.git
    ```

2. Перейти в папку с проектом:

    ```bash
    cd homework_bot
    ```

3. Установить виртуальное окружение для проекта:

    ```
    python -m venv venv
    ```

4. Активировать виртуальное окружение для проекта:

    ```
    # для OS Lunix и MacOS
    source venv/bin/activate

    # для OS Windows
    source venv/Scripts/activate
    ```

5. Установить зависимости:

    ```
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

6. Зарегистрировать чат-бота в Телеграм.

7. Создать в корневой директории файл .env для хранения переменных окружения

    ```
    PRAKTIKUM_TOKEN = 'xxx'
    TELEGRAM_TOKEN = 'xxx'
    TELEGRAM_CHAT_ID = 'xxx'
    ```

8. Запустить проект локально:

    ```
    python homework.py
    ```

## Автор проекта
+ **Алина Туманова** [Tumanova-Alina](https://github.com/Tumanova-Alina)