# Notepad Light for Linux (Debian/Ubuntu)

Легкий текстовый редактор с интерфейсом в стиле Notepad++ для Linux.
Вдохновлен: Официальный проект Notepad++ (Windows): https://github.com/notepad-plus-plus/notepad-plus-plus

## Что реализовано

- вкладки документов (создание, закрытие, перетаскивание вкладок);
- открытие/сохранение файлов (`Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+S`);
- нумерация строк и моноширинный шрифт;
- подсветка синтаксиса по расширению файлов;
- поиск и замена (`Ctrl+F`);
- undo/redo (`Ctrl+Z`, `Ctrl+Y`);
- дублирование строки (`Ctrl+D`);
- статус-бар с текущей позицией курсора;
- сохранение/восстановление сессии между запусками.

## Установка зависимостей (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtksource-3.0
```

## Запуск

```bash
python3 notepadpp_linux.py
```

## Сборка Debian-пакета

Готовый пакет уже собирается из каталога `packaging/notepadpp-linux_1.0.0`.

```bash
mkdir -p dist
dpkg-deb --build packaging/notepadpp-linux_1.0.0 dist/notepadpp-linux_1.0.0_all.deb
```

Установка:

```bash
sudo apt install ./dist/notepadpp-linux_1.0.0_all.deb
```

После установки появятся:
- пункт меню `Notepad Light Linux`;
- иконка приложения (`notepadpp-linux.svg`);
- файловые ассоциации через `.desktop` (`text/plain`, `json`, `xml`, `markdown`, `python`, `shell`, `c/c++`, `java`);
- кастомный MIME-тип `application/x-notepadpp-project` для `*.nppproj`.

## Быстрая упаковка в `.desktop`

Создай файл `~/.local/share/applications/notepadpp-linux.desktop`:

```ini
[Desktop Entry]
Version=1.0.0
Type=Application
Name=Notepad Light Linux
Exec=python3 /ABSOLUTE/PATH/TO/notepadpp_linux.py
Icon=accessories-text-editor
Terminal=false
Categories=Utility;TextEditor;
```

После этого приложение появится в меню системы.
