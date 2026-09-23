# GPT-6 Sol Pro вместо GPT-5.6 Terra Pro

Строка в Notion «Изменения»: https://app.notion.com/p/3e43e7c2538a81728317cec80dc24c55

## Цель
На полке ⚙️ OpenAI стоит модель сильнее и дешевле. Кнопка та же: мама видит новую версию на прежнем месте.

## Доказательства
- Слепой бенч, только эти две модели, 5 задач, судьи Fable 5.1 и Grok 4.7 (Astra Pro пропускает OpenAI): Sol 0.60, Terra 0.40. Sol взяла method, sources, shrink, Terra - edit, terms. Судьи согласны в каждой задаче. `docs/bench-2026-09-23-sol.md`, $0.92.
- Длинный контекст, seed 7, лимит ответа 32000: Sol 8/8, 0 выдуманных, на 100k и на 200k. Terra раньше - 8/8 там же. `docs/longctx-2026-09-23-sol.md`, $1.59.
- Цена выхода: $10 против $12 за 1M.

## Требования
1. `models/slots.yaml`: слот OpenAI workhorse - `openai/gpt-6-sol-pro`, label `GPT-6 Sol Pro`, line `sol-pro`, `out_per_m: 10.0`. `presetId` 275eb791-c305-416d-a53a-e95fb93b4a0b, `rank: 3` и `purpose` прежние.
2. `librechat/librechat.yaml`: в списке «Все» `openai/gpt-6-sol-pro` вместо `openai/gpt-5.6-terra-pro`.
3. `presets/presets.json` и таблица меню в `docs/памятка.md` пересобраны `build_presets.py`: заголовок `⚙️ GPT-6 Sol Pro · 🟢 x4`.
4. Terra не упоминается как текущая модель нигде: CLAUDE.md (таблица полок, порядок меню, пример `line`), комментарий `line` в `slots.yaml`, раздел решений в `docs/model-evaluation-2026-09.md`.
5. Прогоны лежат в `docs/`, решение записано в CLAUDE.md и `docs/model-evaluation-2026-09.md`.

## Не делаем
- Не переписываем прошлые отчёты: строки Terra в `bench-2026-09-22/23.md`, `longctx-2026-09-23*.md` и таблицах `model-evaluation-2026-09.md` - это измерения.
- Не меняем ранг: Sol наследует место Terra (Grok, Opus, Sol).
- `docs/памятка.docx` пересоберёт `memo.yml` после merge.

## Как проверим
1. `validate.py` зелёный.
2. После деплоя в меню `⚙️ GPT-6 Sol Pro · 🟢 x4` на месте Terra, тот же presetId.
3. Вопрос этой кнопке виден в OpenRouter как `openai/gpt-6-sol-pro`.

## Риск и откат
Старые чаты мамы, начатые с Terra, продолжатся на модели чата из меню. Если Sol начнёт отвечать хуже или пропадёт в OpenRouter, revert этого PR возвращает Terra в тот же слот.
