# Длинный контекст 2026-09-23

Рукопись генерируется из seed 7; в неё зашито по 8 противоречий (один и тот же параметр одного образца указан в двух местах по-разному). Модель должна найти все. Проверка по ключу, без судьи. «Нашла» - сколько из зашитых, «выдумала» - сколько названных пар образец/параметр в ключе нет. F1 объединяет обе. Стоимость: $5.85.

## ~50 тыс. токенов (32858-143858 по счёту моделей)

| # | Модель | Нашла | Выдумала | F1 | Секунд |
|---|---|---|---|---|---|
| 1 | Fable 5.1 | 8/8 | 0 | 1.00 | 75 |
| 2 | Opus 5.5 | 8/8 | 0 | 1.00 | 14 |
| 3 | GPT-6 Astra Pro | 8/8 | 0 | 1.00 | 12 |
| 4 | GPT-5.6 Terra Pro | 8/8 | 0 | 1.00 | 11 |
| 5 | GPT-6 Luna Pro | 8/8 | 0 | 1.00 | 25 |
| 6 | Gemini 3.8 Flash | 8/8 | 0 | 1.00 | 57 |
| 7 | Grok 4.7 | 8/8 | 0 | 1.00 | 206 |
| 8 | DeepSeek V4 | 8/8 | 2 | 0.89 | 4 |
| 9 | Sonnet 5 (ответ не JSON) | 0/8 | 0 | 0.00 | 104 |
| 10 | GLM 5.3 (ответ не JSON) | 0/8 | 0 | 0.00 | 39 |
| 11 | Kimi K3 (ответ не JSON) | 0/8 | 0 | 0.00 | 118 |
| 12 | MiniMax M3 (ответ не JSON) | 0/8 | 0 | 0.00 | 608 |

Ключ:

- S-11, дзета: −45 мВ и −18 мВ (раздел 5, фрагмент 15 из 145)
- S-09, дзета: −21 мВ и −42 мВ (раздел 10, фрагмент 78 из 145)
- S-15, lmax: 445 нм и 417 нм (раздел 11, фрагмент 85 из 145)
- S-20, температура: 100 °C и 85 °C (раздел 11, фрагмент 87 из 145)
- S-18, дзета: −35 мВ и −43 мВ (раздел 13, фрагмент 118 из 145)
- S-11, lmax: 445 нм и 440 нм (раздел 14, фрагмент 121 из 145)
- S-02, ph: 9,6 и 6,8 (раздел 14, фрагмент 122 из 145)
- S-02, размер: 57 нм и 39 нм (раздел 14, фрагмент 128 из 145)

## ~200 тыс. токенов (130904-581411 по счёту моделей)

| # | Модель | Нашла | Выдумала | F1 | Секунд |
|---|---|---|---|---|---|
| 1 | GPT-5.6 Terra Pro | 8/8 | 0 | 1.00 | 29 |
| 2 | Grok 4.7 | 8/8 | 0 | 1.00 | 451 |
| 3 | GPT-6 Luna Pro | 5/8 | 1 | 0.71 | 113 |
| 4 | Fable 5.1 (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |
| 5 | Opus 5.5 (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |
| 6 | Sonnet 5 (ответ не JSON) | 0/8 | 0 | 0.00 | 114 |
| 7 | GPT-6 Astra Pro (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |
| 8 | Gemini 3.8 Flash (ответ не JSON) | 0/8 | 0 | 0.00 | 75 |
| 9 | GLM 5.3 (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |
| 10 | Kimi K3 (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |
| 11 | DeepSeek V4 (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |
| 12 | MiniMax M3 (ошибка вызова) | 0/8 | 0 | 0.00 | 0 |

Ключ:

- S-51, pdi: 0,22 и 0,17 (раздел 10, фрагмент 78 из 621)
- S-44, ph: 9,3 и 10,2 (раздел 15, фрагмент 133 из 621)
- S-10, дзета: −42 мВ и −41 мВ (раздел 23, фрагмент 229 из 621)
- S-44, lmax: 424 нм и 429 нм (раздел 38, фрагмент 417 из 621)
- S-06, время: 60 мин и 40 мин (раздел 41, фрагмент 456 из 621)
- S-61, ph: 10,4 и 8,5 (раздел 45, фрагмент 496 из 621)
- S-34, время: 25 мин и 60 мин (раздел 47, фрагмент 519 из 621)
- S-02, температура: 60 °C и 25 °C (раздел 48, фрагмент 533 из 621)

## Ответы

<details><summary>~50k · Fable 5.1</summary>

````
[{"sample": "S-11", "param": "дзета-потенциал", "values": ["−45 мВ", "−18 мВ"]}, {"sample": "S-09", "param": "дзета-потенциал", "values": ["−21 мВ", "−42 мВ"]}, {"sample": "S-15", "param": "максимум плазмонного поглощения", "values": ["445 нм", "417 нм"]}, {"sample": "S-20", "param": "температура синтеза", "values": ["100 °C", "85 °C"]}, {"sample": "S-18", "param": "дзета-потенциал", "values": ["−35 мВ", "−43 мВ"]}, {"sample": "S-11", "param": "максимум плазмонного поглощения", "values": ["445 нм", "440 нм"]}, {"sample": "S-02", "param": "pH реакционной смеси", "values": ["9,6", "6,8"]}, {"sample": "S-02", "param": "средний размер частиц по данным ПЭМ", "values": ["57 нм", "39 нм"]}]
````

</details>

<details><summary>~50k · Opus 5.5</summary>

````
```json
[{"sample": "S-11", "param": "дзета-потенциал", "values": ["−45 мВ", "−18 мВ"]},
{"sample": "S-09", "param": "дзета-потенциал", "values": ["−21 мВ", "−42 мВ"]},
{"sample": "S-20", "param": "температура синтеза", "values": ["100 °C", "85 °C"]},
{"sample": "S-15", "param": "максимум плазмонного поглощения", "values": ["445 нм", "417 нм"]},
{"sample": "S-18", "param": "дзета-потенциал", "values": ["−35 мВ", "−43 мВ"]},
{"sample": "S-11", "param": "максимум плазмонного поглощения", "values": ["445 нм", "440 нм"]},
{"sample": "S-02", "param": "pH реакционной смеси", "values": ["9,6", "6,8"]},
{"sample": "S-02", "param": "средний размер частиц по данным ПЭМ", "values": ["57 нм", "39 нм"]}]
```
````

</details>

<details><summary>~50k · Sonnet 5</summary>

````
(нет ответа: None)
````

</details>

<details><summary>~50k · GPT-6 Astra Pro</summary>

````
[
  {"sample":"S-02","param":"pH реакционной смеси","values":["9,6","6,8"]},
  {"sample":"S-02","param":"средний размер частиц по данным ПЭМ","values":["57 нм","39 нм"]},
  {"sample":"S-09","param":"дзета-потенциал","values":["−21 мВ","−42 мВ"]},
  {"sample":"S-11","param":"дзета-потенциал","values":["−45 мВ","−18 мВ"]},
  {"sample":"S-11","param":"максимум плазмонного поглощения","values":["445 нм","440 нм"]},
  {"sample":"S-15","param":"максимум плазмонного поглощения","values":["445 нм","417 нм"]},
  {"sample":"S-18","param":"дзета-потенциал","values":["−35 мВ","−43 мВ"]},
  {"sample":"S-20","param":"температура синтеза","values":["100 °C","85 °C"]}
]
````

</details>

<details><summary>~50k · GPT-5.6 Terra Pro</summary>

````
[{"sample":"S-11","param":"дзета-потенциал","values":["−45 мВ","−18 мВ"]},{"sample":"S-09","param":"дзета-потенциал","values":["−21 мВ","−42 мВ"]},{"sample":"S-15","param":"максимум плазмонного поглощения","values":["445 нм","417 нм"]},{"sample":"S-20","param":"температура синтеза","values":["100 °C","85 °C"]},{"sample":"S-18","param":"дзета-потенциал","values":["−35 мВ","−43 мВ"]},{"sample":"S-11","param":"максимум плазмонного поглощения","values":["445 нм","440 нм"]},{"sample":"S-02","param":"pH реакционной смеси","values":["9,6","6,8"]},{"sample":"S-02","param":"средний размер частиц по данным ПЭМ","values":["57 нм","39 нм"]}]
````

</details>

<details><summary>~50k · GPT-6 Luna Pro</summary>

````
[
  {"sample":"S-02","param":"pH реакционной смеси","values":["9,6","6,8"]},
  {"sample":"S-02","param":"средний размер частиц по данным ПЭМ","values":["57 нм","39 нм"]},
  {"sample":"S-09","param":"дзета-потенциал","values":["−21 мВ","−42 мВ"]},
  {"sample":"S-11","param":"дзета-потенциал","values":["−45 мВ","−18 мВ"]},
  {"sample":"S-11","param":"максимум плазмонного поглощения","values":["445 нм","440 нм"]},
  {"sample":"S-15","param":"максимум плазмонного поглощения","values":["445 нм","417 нм"]},
  {"sample":"S-18","param":"дзета-потенциал","values":["−35 мВ","−43 мВ"]},
  {"sample":"S-20","param":"температура синтеза","values":["100 °C","85 °C"]}
]
````

</details>

<details><summary>~50k · Gemini 3.8 Flash</summary>

````
[
  {"sample": "S-11", "param": "дзета-потенциал", "values": ["−45 мВ", "−18 мВ"]},
  {"sample": "S-09", "param": "дзета-потенциал", "values": ["−21 мВ", "−42 мВ"]},
  {"sample": "S-15", "param": "максимум плазмонного поглощения", "values": ["445 нм", "417 нм"]},
  {"sample": "S-20", "param": "температура синтеза", "values": ["100 °C", "85 °C"]},
  {"sample": "S-18", "param": "дзета-потенциал", "values": ["−35 мВ", "−43 мВ"]},
  {"sample": "S-11", "param": "максимум плазмонного поглощения", "values": ["445 нм", "440 нм"]},
  {"sample": "S-02", "param": "pH реакционной смеси", "values": ["9,6", "6,8"]},
  {"sample": "S-02", "param": "средний размер частиц по данным ПЭМ", "values": ["57 нм", "39 нм"]}
]
````

</details>

<details><summary>~50k · Grok 4.7</summary>

````
[{"sample": "S-02", "param": "pH реакционной смеси", "values": ["9,6", "6,8"]}, {"sample": "S-02", "param": "средний размер частиц по данным ПЭМ", "values": ["57 нм", "39 нм"]}, {"sample": "S-09", "param": "дзета-потенциал", "values": ["−21 мВ", "−42 мВ"]}, {"sample": "S-11", "param": "дзета-потенциал", "values": ["−45 мВ", "−18 мВ"]}, {"sample": "S-11", "param": "максимум плазмонного поглощения", "values": ["445 нм", "440 нм"]}, {"sample": "S-15", "param": "максимум плазмонного поглощения", "values": ["445 нм", "417 нм"]}, {"sample": "S-18", "param": "дзета-потенциал", "values": ["−35 мВ", "−43 мВ"]}, {"sample": "S-20", "param": "температура синтеза", "values": ["100 °C", "85 °C"]}]
````

</details>

<details><summary>~50k · GLM 5.3</summary>

````
(нет ответа: None)
````

</details>

<details><summary>~50k · Kimi K3</summary>

````
(нет ответа: None)
````

</details>

<details><summary>~50k · DeepSeek V4</summary>

````
```json
[
  {
    "sample": "S-02",
    "param": "pH реакционной смеси",
    "values": ["9,6", "6,8"]
  },
  {
    "sample": "S-02",
    "param": "средний размер частиц по данным ПЭМ",
    "values": ["57 нм", "39 нм"]
  },
  {
    "sample": "S-09",
    "param": "дзета-потенциал",
    "values": ["−21 мВ", "−42 мВ"]
  },
  {
    "sample": "S-11",
    "param": "дзета-потенциал",
    "values": ["−45 мВ", "−18 мВ"]
  },
  {
    "sample": "S-11",
    "param": "максимум плазмонного поглощения",
    "values": ["445 нм", "440 нм"]
  },
  {
    "sample": "S-15",
    "param": "максимум плазмонного поглощения",
    "values": ["445 нм", "417 нм"]
  },
  {
    "sample": "S-16",
    "param": "температура синтеза",
    "values": ["90 °C", "60 °C"]
  },
  {
    "sample": "S-18",
    "param": "дзета-потенциал",
    "values": ["−35 мВ", "−43 мВ"]
  },
  {
    "sample": "S-20",
    "param": "температура синтеза",
    "values": ["100 °C", "85 °C"]
  },
  {
    "sample": "S-12",
    "param": "температура синтеза",
    "values": ["60 °C", "60 °C"]
  }
]
```
````

</details>

<details><summary>~50k · MiniMax M3</summary>

````
(нет ответа: None)
````

</details>

<details><summary>~200k · Fable 5.1</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

<details><summary>~200k · Opus 5.5</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

<details><summary>~200k · Sonnet 5</summary>

````
(нет ответа: None)
````

</details>

<details><summary>~200k · GPT-6 Astra Pro</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

<details><summary>~200k · GPT-5.6 Terra Pro</summary>

````
[{"sample":"S-02","param":"температура синтеза","values":["60 °C","25 °C"]},{"sample":"S-06","param":"время выдержки","values":["60 мин","40 мин"]},{"sample":"S-10","param":"дзета-потенциал","values":["−42 мВ","−41 мВ"]},{"sample":"S-34","param":"время выдержки","values":["25 мин","60 мин"]},{"sample":"S-44","param":"pH реакционной смеси","values":["9,3","10,2"]},{"sample":"S-44","param":"максимум плазмонного поглощения","values":["424 нм","429 нм"]},{"sample":"S-51","param":"индекс полидисперсности","values":["0,22","0,17"]},{"sample":"S-61","param":"pH реакционной смеси","values":["10,4","8,5"]}]
````

</details>

<details><summary>~200k · GPT-6 Luna Pro</summary>

````
[
  {
    "sample": "S-10",
    "param": "дзета-потенциал",
    "values": ["−42 мВ", "−41 мВ"]
  },
  {
    "sample": "S-34",
    "param": "время выдержки",
    "values": ["25 мин", "60 мин"]
  },
  {
    "sample": "S-44",
    "param": "pH реакционной смеси",
    "values": ["9,3", "10,2"]
  },
  {
    "sample": "S-44",
    "param": "максимум плазмонного поглощения",
    "values": ["424 нм", "429 нм"]
  },
  {
    "sample": "S-51",
    "param": "индекс полидисперсности",
    "values": ["0,22", "0,17"]
  },
  {
    "sample": "S-58",
    "param": "время выдержки",
    "values": ["30 мин", "25 мин"]
  }
]
````

</details>

<details><summary>~200k · Gemini 3.8 Flash</summary>

````
: zeta -21 mV (correct)
S-05: zeta -37 mV (correct)
S-70: SPR 453 nm (correct)
S-51: PDI 0.22 (correct)

Section 19:
S-74: d 10 nm (correct)
S-16: PDI 0.38 (correct)
S-22: d 50 nm (correct)
S-31: zeta -28 mV (correct)
S-14: pH 7.5 (correct)
S-58: temp 40 °C (correct)
S-22: temp 60 °C (correct)
S-19: pH 6.4 (correct)
S-59: temp 40 °C (correct)
S-34: PDI 0.19 (correct)
S-17: d 34 nm (correct)
S-23: temp 95 °C (correct)
S-57: SPR 448 nm (correct)
S-35: SPR 432 nm (correct)
S-29: zeta -34 mV (correct)
S-80: PDI 0.44 (correct)
S-61: pH 10.4 (correct)
S-20: time 90 min (correct)
S-54: temp 60 °C (correct)
S-26: PDI 0.17 (correct)
S-46: temp 95 °C (correct)
S-56: temp 20 °C (correct)
S-71: time 60 min (correct)
S-25: PDI 0.10 (correct)
S-62: time 25 min (correct)
S-78: pH 6.8 (correct)
S-77: temp 85 °C (correct)
S-61: temp 20 °C (correct)
S-76: SPR 447 nm (correct)
S-15: SPR 444 nm (correct)
S-23: temp 95 °C (correct)
S-31: zeta -28 mV (correct)
S-46: d 16 nm (correct)
S-53: pH 9.7 (correct)
S-06: SPR 448 nm (correct)
S-09: PDI 0.26 (correct)
S-26: PDI 0.17 (correct)
S-70: PDI 0.18 (correct)
S-26: zeta -48 mV (correct)
S
````

</details>

<details><summary>~200k · Grok 4.7</summary>

````
[{"sample": "S-02", "param": "температура синтеза", "values": ["60 °C", "25 °C"]}, {"sample": "S-06", "param": "время выдержки", "values": ["60 мин", "40 мин"]}, {"sample": "S-10", "param": "дзета-потенциал", "values": ["−42 мВ", "−41 мВ"]}, {"sample": "S-34", "param": "время выдержки", "values": ["25 мин", "60 мин"]}, {"sample": "S-44", "param": "pH реакционной смеси", "values": ["9,3", "10,2"]}, {"sample": "S-44", "param": "максимум плазмонного поглощения", "values": ["424 нм", "429 нм"]}, {"sample": "S-51", "param": "индекс полидисперсности", "values": ["0,22", "0,17"]}, {"sample": "S-61", "param": "pH реакционной смеси", "values": ["10,4", "8,5"]}]
````

</details>

<details><summary>~200k · GLM 5.3</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

<details><summary>~200k · Kimi K3</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

<details><summary>~200k · DeepSeek V4</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

<details><summary>~200k · MiniMax M3</summary>

````
(нет ответа: HTTP Error 402: Payment Required)
````

</details>

