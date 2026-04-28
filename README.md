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
- сохранение/восстановление сессии между запусками;
- темная тема редактора;
- выбор кодировки открытого файла;
- ручной выбор языка подсветки синтаксиса.

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

Готовый пакет собирается из каталога `packaging/notepadpp-linux_1.1.4`.

```bash
mkdir -p dist
dpkg-deb --root-owner-group --build packaging/notepadpp-linux_1.1.4 dist/notepadpp-linux_1.1.4_all.deb
```

Установка:

```bash
sudo apt install ./dist/notepadpp-linux_1.1.4_all.deb
```

После установки появятся:
- пункт меню `Notepad Light Linux`;
- иконка приложения (`notepadpp-linux.svg`);
- файловые ассоциации через `.desktop` (`text/plain`, `csv`, `markdown`, `html`, `css`, `json`, `xml`, `yaml`, `sql`, `python`, `javascript`, `typescript`, `shell`, `c/c++`, `java`, `go`, `rust`);
- приложение назначается основным для поддерживаемых MIME-типов на уровне `/usr/share/applications/mimeapps.list`;
- кастомный MIME-тип `application/x-notepadpp-project` для `*.nppproj`.

## История изменений

### 1.1.4

- Исправлено открытие файлов из файлового проводника: выбранный файл теперь передается приложению через `Gtk.Application.do_open()` и открывается в новой вкладке.
- Приложение после установки назначается основным для поддерживаемых типов файлов.
- Расширен список MIME-типов в `.desktop` для поддерживаемых языков и текстовых форматов.
- Добавлена очистка системных MIME-назначений при удалении пакета.
- Добавлена защита от запуска из Snap-окружения VS Code, из-за которого GTK мог подхватывать несовместимые библиотеки Snap `core20`.
- Код приложения разнесен на пакет `notepadpp_app` с отдельными модулями запуска, настроек и GTK-интерфейса.
- Исправлено переключение вкладок, создание новой вкладки и открытие файла в новой вкладке из диалога выбора файла.
- Исправлено зацикливание переключения вкладок и radio-пунктов меню кодировки/подсветки.
- Исправлено применение ручного выбора языка подсветки синтаксиса.
- Обновлена подсветка языка 1С из `languages/1c-ent.lang`; добавлена поддержка файлов `*.bsl` и `*.os`.
- Исправлено переключение кодировок: неподходящая кодировка больше не приводит к ошибке `truncated data`, текст отображается с заменой некорректных символов.
- Темная тема теперь применяется к области редактора, а не только к выпадающим меню.
- Пакетная копия `packaging/notepadpp-linux_1.1.4` синхронизирована с актуальными исходниками.

## Быстрая упаковка в `.desktop`

Создай файл `~/.local/share/applications/notepadpp-linux.desktop`:

```ini
[Desktop Entry]
Version=1.1.4
Type=Application
Name=Notepad Light Linux
Exec=python3 /ABSOLUTE/PATH/TO/notepadpp_linux.py
Icon=accessories-text-editor
Terminal=false
Categories=Utility;TextEditor;
```

После этого приложение появится в меню системы.
