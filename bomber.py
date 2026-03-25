name: Build BOMBO4KA APK
on: [push, workflow_dispatch]

jobs:
  build:
    runs-on: ubuntu-22.04  # Откатываемся на более стабильную версию для Buildozer
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install System Dependencies
        run: |
          sudo apt update
          sudo apt install -y git zip unzip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev libbz2-dev libsqlite3-dev
          sudo apt install -y openjdk-17-jdk  # Принудительно ставим 17-ю Java
          pip install --upgrade pip
          pip install buildozer cython virtualenv

      - name: Build APK with Buildozer
        run: |
          # Очистка старых попыток
          rm -rf .buildozer
          
          # Инициализация
          buildozer init
          
          # Настройка конфига
          sed -i 's/package.name = myapp/package.name = bombo4ka/' buildozer.spec
          sed -i 's/package.domain = org.test/package.domain = com.bombo4ka/' buildozer.spec
          sed -i 's/source.include_exts = py,png,jpg,kv,atlas/source.include_exts = py,png,html,json,txt,css,js/' buildozer.spec
          sed -i 's/source.main = main.py/source.main = bomber.py/' buildozer.spec
          
          # Указываем правильную версию Android API (33 сейчас стандарт для Google Play)
          sed -i 's/android.api = 31/android.api = 33/' buildozer.spec
          
          # Запуск сборки
          buildozer -v android debug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: BOMBO4KA-Android-App
          path: bin/*.apk
