#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape


REFERENCE = Path.home() / ".vscode/extensions/1c-syntax.language-1c-bsl-1.32.1/lib/bslGlobals.json"
ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "languages/1c-ent.lang",
    ROOT / "packaging/notepadpp-linux_1.1.4/usr/share/notepadpp-linux/languages/1c-ent.lang",
]


def names_from_items(items: dict) -> list[str]:
    names: set[str] = set()
    for item in items.values():
        name = item.get("name")
        name_en = item.get("name_en")
        if name:
            names.add(name)
        if name_en:
            names.add(name_en)
    return sorted(names, key=str.casefold)


def preferred_function_names(items: dict, limit: int = 260) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in items.values():
        for key in ("name", "name_en"):
            name = item.get(key)
            if name and name not in seen:
                names.append(name)
                seen.add(name)
    priority = {
        "Сообщить",
        "Message",
        "ЗначениеЗаполнено",
        "ValueIsFilled",
        "НСтр",
        "NStr",
        "НачатьТранзакцию",
        "BeginTransaction",
        "ЗафиксироватьТранзакцию",
        "CommitTransaction",
        "ОтменитьТранзакцию",
        "RollbackTransaction",
        "ЗаписатьJSON",
        "WriteJSON",
        "ПрочитатьJSON",
        "ReadJSON",
        "Base64Значение",
        "Base64Value",
        "ACos",
        "ASin",
        "ATan",
        "Cos",
        "Sin",
        "Sqrt",
        "Tan",
    }
    names.sort(key=lambda name: (name not in priority, name.casefold()))
    return names[:limit]


def enum_names(items: dict) -> list[str]:
    names: set[str] = set()
    for item in items.values():
        name = item.get("name")
        name_en = item.get("name_en")
        if name:
            names.add(name)
        if name_en:
            names.add(name_en)
    return sorted(names, key=str.casefold)


def keyword_lines(words: list[str], indent: str = "      ") -> str:
    return "\n".join(f"{indent}<keyword>{escape(word)}</keyword>" for word in words)


def regex_alt(words: list[str]) -> str:
    return "|".join(re.escape(word) for word in words)


def chunked(words: list[str], size: int) -> list[list[str]]:
    return [words[i : i + size] for i in range(0, len(words), size)]


def function_contexts(functions: list[str]) -> str:
    parts = []
    for index, chunk in enumerate(chunked(functions, 90), start=1):
        parts.append(
            f'''    <context id="builtin-functions-{index}" style-ref="function">
{keyword_lines(chunk)}
    </context>'''
        )
    return "\n".join(parts)


def word_contexts(context_id: str, style: str, words: list[str], size: int = 120) -> str:
    parts = []
    for index, chunk in enumerate(chunked(words, size), start=1):
        parts.append(
            f'''    <context id="{context_id}-{index}" style-ref="{style}">
{keyword_lines(chunk)}
    </context>'''
        )
    return "\n".join(parts)


def refs(context_id: str, words: list[str], size: int = 120) -> str:
    return "\n".join(
        f'        <context ref="{context_id}-{index}"/>'
        for index, _chunk in enumerate(chunked(words, size), start=1)
    )


def main() -> None:
    if not REFERENCE.exists():
        raise SystemExit(f"Missing VS Code BSL reference: {REFERENCE}")

    data = json.loads(REFERENCE.read_text(encoding="utf-8"))
    keywords = sorted(
        set(data["keywords"]["ru"]) | set(data["keywords"]["en"]),
        key=str.casefold,
    )
    constants = ["Неопределено", "Undefined", "Истина", "True", "Ложь", "False", "NULL"]
    functions = preferred_function_names(data["globalfunctions"])
    variables: list[str] = []
    classes: list[str] = []
    # GtkSourceView 3.0 combines many transitions into one regex. The full
    # 1C enum list is large enough to trigger "regular expression is too large",
    # so enums stay out of the generated highlighter for now.
    enums: list[str] = []
    storage_words = [
        "Процедура",
        "Procedure",
        "Функция",
        "Function",
        "КонецПроцедуры",
        "EndProcedure",
        "КонецФункции",
        "EndFunction",
        "Перем",
        "Var",
        "Экспорт",
        "Export",
        "Знач",
        "Val",
    ]
    storage_words = sorted(set(storage_words + [word.lower() for word in storage_words]), key=str.casefold)
    control_words = [word for word in keywords if word not in constants]
    control_words = sorted(set(control_words + [word.lower() for word in control_words]), key=str.casefold)
    constant_words = sorted(set(constants + [word.lower() for word in constants]), key=str.casefold)

    text = f'''<?xml version="1.0" encoding="UTF-8"?>
<language id="1c-ent" name="1C Enterprise" version="2.0" _section="Sources">
  <metadata>
    <property name="mimetypes">text/x-1c-ent</property>
    <property name="globs">*.os;*.bsl</property>
    <property name="line-comment-start">//</property>
    <property name="block-comment-start">/*</property>
    <property name="block-comment-end">*/</property>
  </metadata>
  <styles>
    <style id="comment" name="Comment" map-to="def:comment"/>
    <style id="string" name="String" map-to="def:string"/>
    <style id="keyword" name="Keyword" map-to="def:keyword"/>
    <style id="storage" name="Storage" map-to="def:type"/>
    <style id="modifier" name="Modifier" map-to="def:keyword"/>
    <style id="operator" name="Operator" map-to="def:operator"/>
    <style id="variable" name="Variable" map-to="def:identifier"/>
    <style id="parameter" name="Parameter" map-to="def:identifier"/>
    <style id="number" name="Number" map-to="def:number"/>
    <style id="preprocessor" name="Preprocessor" map-to="def:preprocessor"/>
    <style id="section" name="Section" map-to="def:preprocessor"/>
    <style id="constant" name="Constant" map-to="def:constant"/>
    <style id="function" name="Builtin Function" map-to="def:builtin"/>
    <style id="class" name="Class" map-to="def:type"/>
    <style id="global-variable" name="Global Variable" map-to="def:identifier"/>
    <style id="enum" name="System Enum" map-to="def:type"/>
    <style id="date-const" name="Date Constant" map-to="def:special-constant"/>
    <style id="annotation" name="Annotation" map-to="def:preprocessor"/>
    <style id="query" name="Query" map-to="def:keyword"/>
  </styles>
  <definitions>
    <context id="1c-ent" class="no-spell-check">
      <include>
        <context ref="line-comment"/>
        <context ref="block-comment"/>
        <context ref="string-double"/>
        <context ref="date-constant"/>
        <context ref="number"/>
        <context ref="procedure-declaration"/>
        <context ref="variable-declaration"/>
        <context ref="assignment-target"/>
        <context ref="known-directives"/>
        <context ref="annotations"/>
        <context ref="preprocessor-if"/>
        <context ref="preprocessor-section"/>
{refs("constants", constant_words)}
{refs("storage-keywords", storage_words)}
{refs("control-keywords", control_words)}
        <context ref="operators"/>
{refs("builtin-functions", functions, 90)}
{refs("global-variables", variables)}
{refs("classes", classes)}
{refs("system-enums", enums)}
      </include>
    </context>

    <context id="line-comment" style-ref="comment">
      <start>//</start>
      <end>$</end>
    </context>

    <context id="block-comment" style-ref="comment">
      <start>/\\*</start>
      <end>\\*/</end>
      <include>
        <context ref="block-comment"/>
      </include>
    </context>

    <context id="string-double" style-ref="string">
      <start>"</start>
      <end>"(?!")</end>
      <include>
        <context ref="escaped-quote"/>
        <context ref="query-keywords"/>
      </include>
    </context>

    <context id="escaped-quote" style-ref="string">
      <match>""</match>
    </context>

    <context id="date-constant" style-ref="date-const">
      <match>'(([0-9]{{4}}[^0-9']*[0-9]{{2}}[^0-9']*[0-9]{{2}})([^0-9']*[0-9]{{2}}[^0-9']*[0-9]{{2}}([^0-9']*[0-9]{{2}})?)?)'</match>
    </context>

    <context id="number" style-ref="number">
      <match>(?&lt;![A-Za-zА-Яа-яЁё0-9_\\.])[0-9]+(\\.[0-9]+)?(?![A-Za-zА-Яа-яЁё0-9_])</match>
    </context>

    <context id="procedure-declaration">
      <match>(?i)\\b(Процедура|Procedure|Функция|Function)\\s+([A-Za-zА-Яа-яЁё0-9_]+)</match>
      <include>
        <context id="procedure-kind" sub-pattern="1" style-ref="storage"/>
        <context id="procedure-name" sub-pattern="2" style-ref="function"/>
      </include>
    </context>

    <context id="variable-declaration">
      <match>(?i)\\b(Перем|Var)\\s+([A-Za-zА-Яа-яЁё0-9_]+)</match>
      <include>
        <context id="var-kind" sub-pattern="1" style-ref="storage"/>
        <context id="var-name" sub-pattern="2" style-ref="variable"/>
      </include>
    </context>

    <context id="assignment-target">
      <match>(?i)(^|;)\\s*([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)\\s*(?==)</match>
      <include>
        <context id="assignment-name" sub-pattern="2" style-ref="variable"/>
      </include>
    </context>

    <context id="known-directives" style-ref="annotation">
      <match>(?i)&amp;(НаКлиенте((НаСервере(БезКонтекста)?)?)|AtClient((AtServer(NoContext)?)?)|НаСервере(БезКонтекста)?|AtServer(NoContext)?)</match>
    </context>

    <context id="annotations" style-ref="annotation">
      <match>(?i)&amp;([A-Za-zА-Яа-яЁё0-9_]+)</match>
    </context>

    <context id="preprocessor-if" style-ref="preprocessor">
      <match>(?i)^\\s*#(Если|If|ИначеЕсли|ElsIf|Иначе|Else|КонецЕсли|EndIf).*$</match>
    </context>

    <context id="preprocessor-section" style-ref="section">
      <match>(?i)^\\s*#(Область|Region|КонецОбласти|EndRegion|Удаление|Delete|КонецУдаления|EndDelete|Вставка|Insert|КонецВставки|EndInsert|Использовать|Use|native).*$</match>
    </context>

{word_contexts("constants", "constant", constant_words)}

{word_contexts("storage-keywords", "storage", storage_words)}

{word_contexts("control-keywords", "keyword", control_words)}

    <context id="operators" style-ref="operator">
      <match>(?i)(&lt;=|&gt;=|=|&lt;|&gt;|\\+|-|\\*|/|%|;|\\?|,|\\(|\\)|\\b(НЕ|NOT|И|AND|ИЛИ|OR)\\b)</match>
    </context>

{function_contexts(functions)}

{word_contexts("global-variables", "global-variable", variables)}

{word_contexts("classes", "class", classes)}

{word_contexts("system-enums", "enum", enums)}

    <context id="query-keywords" style-ref="query">
      <match>(?i)\\b(ВЫБРАТЬ|ВЫБРАТЬ\\s+РАЗРЕШЕННЫЕ|Select|ИЗ|From|ГДЕ|Where|КАК|As|ИТОГИ|Totals|ПО|By|СГРУППИРОВАТЬ|Group|УПОРЯДОЧИТЬ|Order|ОБЪЕДИНИТЬ|Union|ПЕРВЫЕ|Top|РАЗЛИЧНЫЕ|Distinct|ЛЕВОЕ|Left|ПРАВОЕ|Right|ВНУТРЕННЕЕ|Inner|СОЕДИНЕНИЕ|Join)\\b</match>
    </context>
  </definitions>
</language>
'''
    for target in TARGETS:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
