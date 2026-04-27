# Notepad Light for Linux (Debian/Ubuntu)

Легкий текстовый редактор с интерфейсом в стиле Notepad++ для Linux.
Вдохновлен: [Официальный проект Notepad++ (Windows)](https://github.com/notepad-plus-plus/notepad-plus-plus)

**Версия:** 1.1.3

## Возможности

- **Вкладки документов** — создание, закрытие, перетаскивание (`Ctrl+W` — закрыть, `Ctrl+N` — новый);
- **Открытие/сохранение файлов** — `Ctrl+O` (открыть), `Ctrl+S` (сохранить), `Ctrl+Shift+S` (сохранить как);
- **Диалог Save As с выбором типа файла** — выбор языка подсветки из выпадающего списка, автоматическая подстановка расширения;
- **Подсветка синтаксиса** — автоматическое определение языка по расширению файла;
- **Меню Syntax Highlight** — ручной выбор подсветки (Plain Text, CSV, Markdown, XML, JSON, 1C Enterprise, Python, JavaScript, TypeScript, HTML, CSS, C, C++, Java, Shell, YAML, SQL, Go, Rust);
- **1C Enterprise (BSL/OneScript)** — полноценная подсветка для `.os` и `.bsl` файлов: ключевые слова, встроенные функции, аннотации `&НаКлиенте`/`&AtServer`, даты, числа, строки, комментарии, препроцессор (`#Область`, `#Если`, `#Использовать`);
- **CSV подсветка** — для `.csv` файлов;
- **Кодировки** — поддержка UTF-8, UTF-16, Windows-1251, Windows-1252, CP866, KOI8-R, ISO-8859-1 с переключением через меню Encoding;
- **Поиск и замена** — `Ctrl+F` с поддержкой replace;
- **Undo/Redo** — `Ctrl+Z`, `Ctrl+Y`;
- **Дублирование строки** — `Ctrl+D`;
- **Word Wrap** — перенос по словам (меню View > Word Wrap);
- **Тёмная тема** — встроенная тёмная тема (меню View > Dark Theme), правильная подсветка синтаксиса при переключении темы — автоматически выбирается тёмная (oblivion) или светлая (classic) схема GtkSourceView;
- **Статус-бар** — отображение пути к файлу, кодировки, языка подсветки, позиции курсора (Ln/Col);
- **Клик по Ctrl+ссылка** — открытие URL в браузере;
- **Сохранение/восстановление сессии** — между запусками запоминает открытые вкладки и позицию;
- **Иконка приложения** — собственная иконка в окне и панели задач.

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

```bash
mkdir -p dist
dpkg-deb --build packaging/notepadpp-linux_1.1.3 dist/notepadpp-linux_1.1.3_all.deb
```

Установка:

```bash
sudo apt install ./dist/notepadpp-linux_1.1.3_all.deb
```

После установки появятся:

- пункт меню **Notepad Light Linux**;
- иконка приложения (`notepadpp-linux.svg`);
- файловые ассоциации через `.desktop` (`text/plain`, `json`, `xml`, `markdown`, `python`, `shell`, `c/c++`, `java`);
- кастомный MIME-тип `application/x-notepadpp-project` для `*.nppproj`.

## Быстрая упаковка в `.desktop`

Создай файл `~/.local/share/applications/notepadpp-linux.desktop`:

```ini
[Desktop Entry]
Version=1.1.3
Type=Application
Name=Notepad Light Linux
Exec=python3 /ABSOLUTE/PATH/TO/notepadpp_linux.py
Icon=accessories-text-editor
Terminal=false
Categories=Utility;TextEditor;
```

После этого приложение появится в меню системы.

## История изменений

### 1.1.3
- Исправлена подсветка 1C Enterprise для GtkSourceView 3.0 — полностью переписан `1c-ent.lang`
  - Устранена проблема с `<` в `<match>` элементах (libxml2 GtkSourceView ломался на декодированных `<`)
  - Ключевые слова, константы, директивы препроцессора переведены на `<keyword>` элементы
  - Добавлен `class="no-spell-check"` на корневой контекст (обязательно для GtkSourceView 3.x)
  - Экранированы `*` в `<start>`/`<end>` block-комментариев
- Добавлена иконка приложения — PNG 256x256 из `icon/notepadpp_icon_256_transparent.png`

### 1.1.2
- Исправлено определение языка после смены через меню Syntax Highlight

### 1.1.0
- Добавлено меню Syntax Highlight с ручным выбором языка подсветки
- Добавлен диалог Save As с выбором типа файла
- 1C Enterprise подсветка: ключевые слова, встроенные функции, аннотации, препроцессор
- CSV подсветка

## Структура проекта

```markdown
.
├── notepadpp_linux.py          # основной исполняемый файл
├── README.md
├── icon/
│   └── notepadpp_icon_256_transparent.png
├── languages/
│   ├── 1c-ent.lang             # подсветка 1C Enterprise (BSL/OneScript)
│   └── csv.lang                # подсветка CSV
├── packaging/
│   ├── notepadpp-linux_1.0.0/  # deb-пакет v1.0.0
│   ├── notepadpp-linux_1.0.1/  # deb-пакет v1.0.1
│   ├── notepadpp-linux_1.1.0/  # deb-пакет v1.1.0
│   ├── notepadpp-linux_1.1.2/  # deb-пакет v1.1.2
│   └── notepadpp-linux_1.1.3/  # deb-пакет v1.1.3 (текущий)
├── plans/
│   └── v1.1.0-syntax-highlight-menu.md
└── dist/                       # собранные .deb пакеты
```
