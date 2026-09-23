// Builds docs/памятка.docx - the printable памятка for the mother (Word).
// docs/памятка.md is the short version the helper «❓ Какую кнопку?» reads;
// this is the long one she keeps. Both name the menu's models by their
// labels from models/slots.yaml, so a monthly replacement edits the label
// here too, then rebuilds (gate_check.py fails while an old label is left).
//
// Usage: node scripts/memo_docx.js           # writes docs/памятка.docx
//        node scripts/memo_docx.js --check   # exit 1 if the .docx is stale
// --check compares every part of the file except docProps/core.xml, which
// only carries the build time.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  HeadingLevel, AlignmentType, ShadingType, BorderStyle, LevelFormat, PageBreak,
} = require("docx");

const FONT = "Calibri";
const B = { bold: true };
const GREY = { italics: true, color: "595959" };

const run = (t, o = {}) => new TextRun({ text: t, font: FONT, size: 22, ...o });
const p = (children, o = {}) => new Paragraph({ children: Array.isArray(children) ? children : [run(children)], spacing: { after: 120 }, ...o });
const h = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })], spacing: { before: 280, after: 120 } });
const rich = (parts) => p(parts.map((x) => (typeof x === "string" ? run(x) : run(x[0], x[1] || {}))), { spacing: { after: 0 } });
const cell = (content, width, o = {}) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [typeof content === "string" ? p(content, { spacing: { after: 0 } }) : Array.isArray(content) ? rich(content) : content],
  ...o,
});
const head = (labels, widths) => new TableRow({
  tableHeader: true,
  children: labels.map((l, i) => cell(rich([[l, B]]), widths[i], { shading: { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } })),
});
const band = (label, widths) => new TableRow({
  children: [cell(rich([[label, { bold: true, color: "404040" }]]), widths.reduce((a, b) => a + b, 0), { columnSpan: widths.length, shading: { type: ShadingType.CLEAR, fill: "F2F2F2", color: "auto" } })],
});
const row = (cells, widths) => new TableRow({ children: cells.map((c, i) => cell(c, widths[i])) });
const table = (rows, widths) => new Table({ columnWidths: widths, width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, rows });
const box = (fill, line, children) => new Paragraph({
  spacing: { before: 60, after: 120 },
  shading: { type: ShadingType.CLEAR, fill, color: "auto" },
  border: { left: { style: BorderStyle.SINGLE, size: 24, color: line, space: 8 } },
  children,
});
const item = (ref, bold, text) => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 100 }, children: [run(bold, B), run(text)] });

const TW = [3500, 2500, 3360];
const tasks = [
  ["С вопросом и задачей"],
  ["Любой вопрос, обсудить, не знаю, с чего начать", [["🧭 Новый вопрос", B]], "Сначала задаст до трёх уточняющих вопросов, потом ответит: суть, ниже детали"],
  ["Анализ данных, механизм, написать раздел, термины, перевод", [["🧭 Новый вопрос", B], " или ", ["⚙️ Opus 5.5", B]], "Точен в цифрах и терминах. Кнопка 🧭 - тот же Opus, только сначала уточнит"],
  ["Выбрать: методика, план эксперимента, как улучшить готовое", [["🎛 Варианты", B]], "Пять разных вариантов с «за» и «против», в конце - какой взял бы сам"],
  ["С текстом"],
  ["Исправить свой текст, но чтобы остался мой", [["✏️ Править текст", B]], "Исправит ошибки, смысл и стиль не тронет, в конце список правок. До 40 страниц, больше - по главам"],
  ["Проверить статью, главу, диплом студентки целиком", [["🔍 Рецензия", B]], "Ошибки и нестыковки по пунктам, с цитатой. Сам текст не переписывает. Держит 200 страниц"],
  ["Прочитать статью или НИР до 20 страниц и спросить по ней", [["⚙️ Grok 4.7", B]], "Не ошибается и дёшев, но думает около минуты. Быстрее - 🧠 Astra Pro"],
  ["Большой документ, 60–200 страниц", [["🧠 Astra Pro", B], ", в два шага"], "Шаги ниже, в разделе 3"],
  ["Поиск литературы, запросы в Scopus", [["🧠 Astra Pro", B]], "Остальные выдумывают операторы поиска"],
  ["Сократить абзац, набросать черновик плана", [["⚡ Luna", B]], "Справляется отлично, почти бесплатно"],
  ["Жизнь"],
  ["Цветы, рецепты, письмо, куда пойти с детьми", [["⚡ Luna", B], " или ", ["⚡ Gemini Flash", B]], "Копейки"],
  ["Здоровье, лекарства, что-то важное", [["⚙️ Opus 5.5", B]], "И к врачу, а не вместо"],
];

const SW = [2200, 2800, 4360];
const sizes = [
  ["до 20 страниц", "статья, отчёт, глава", "любая кнопка"],
  ["20–60 страниц", "НИР, большой отчёт", [["любая, ", {}], ["кроме Fable и ✏️ Править текст", B]]],
  ["60–200 страниц", "диссертация, диплом, монография", [["только 🧠 Astra Pro, 🔍 Рецензия или ⚙️ Opus", B]]],
];

const MW = [3900, 1300, 4160];
const menu = [
  ["Кнопки с готовым порядком работы"],
  [[["❓ Какую кнопку?", B]], "x0", "Luna"],
  [[["🧭 Новый вопрос", B]], "x8", "Opus 5.5"],
  [[["✏️ Править текст", B]], "x20", "Fable 5.1"],
  [[["🔍 Рецензия", B]], "x20", "Astra Pro"],
  [[["🎛 Варианты", B]], "x8", "Opus 5.5"],
  ["Просто модели: 🧠 сильнейшие, ⚙️ рабочие, ⚡ выгодные"],
  [[["🧠 Fable 5.1", B]], "x20", "Править текст. Не для текстов длиннее 40 страниц"],
  [[["🧠 GPT-6 Astra Pro", B]], "x20", "Большие документы, литература"],
  [[["⚙️ Grok 4.7", B]], "x2", "Статья или НИР до 20 страниц"],
  [[["⚙️ Opus 5.5", B]], "x8", "Всё, когда не знаешь"],
  [[["⚙️ GPT-5.6 Terra Pro", B]], "x5", "Запасная для больших документов"],
  [[["⚡ GPT-6 Luna Pro", B]], "x0", "Мелочь, быт, черновик"],
  [[["⚡ Gemini 3.8 Flash", B]], "x2", "Быстрый вопрос, быт"],
];

const HW = [3700, 2300, 3360];
const habits = [
  ["Всегда"],
  [[["1. Контекст. ", B], "Файл в приложении лучше пересказа. Модель не должна угадывать"], [["сама", B]], "Главное правило, ниже - что прикладывать"],
  [[["2. Формализация. ", B], "«Ничего не додумывай. Не знаешь - так и скажи. Не проверено - пометь»"], [["уже в каждой кнопке", { bold: true, color: "548235" }]], "Писать не надо"],
  [[["3. Новый чат на задачу. ", B], "Старый чат пересылается целиком с каждым сообщением: дороже и хуже"], [["сама", B]], "Кнопка «новый чат» слева сверху"],
  ["По случаю"],
  [[["4. Заготовки. ", B], "Типовые запросы держать готовыми"], [["это и есть кнопки", { bold: true, color: "548235" }]], "🧭 ✏️ 🔍 🎛 наверху меню"],
  [[["5. Краткость. ", B], "«Сначала суть в 2–3 предложениях, детали ниже»"], [["🧭 Новый вопрос", B]], "Отвечает так сам"],
  [[["6. Уточнение. ", B], "«Прежде чем отвечать, задай мне по одному вопросы». По одному - ответ на первый меняет второй"], [["🧭 Новый вопрос", B]], "Задаёт до трёх вопросов, по одному. Простой вопрос - сразу отвечает"],
  [[["7. Обоснование. ", B], "«Обоснуй ответ. Ссылок не выдумывай: скажи, что и где искать»"], [["🔍 Рецензия", B], ", частично везде"], "«Ссылок не выдумывай» есть в каждой кнопке. «Обоснуй» допиши сама, где нужно"],
  [[["8. Варианты. ", B], "«Дай 5 вариантов, обоснуй каждый» - выбирать проще, чем принять один"], [["🎛 Варианты", B]], "Пять вариантов, «за», «против», свой выбор"],
  [[["9. Улучшения. ", B], "Получила решение - не применяй сразу, спроси, как улучшить"], [["🎛 Варианты", B]], "Вставь готовое решение и напиши «улучши»"],
  [[["10. Второе мнение. ", B], "Важный вывод проверить моделью другой компании"], [["🔍 Рецензия", B]], "Там GPT, а 🧭 и 🎛 - Claude. Компании уже разные"],
];
const context = [
  ["файлы", "статьи, выжимки, дипломы"],
  ["данные", "таблицы, скриншоты, картинки"],
  ["цель", "что хочешь получить и зачем"],
  ["специфику", "чем твой случай отличается от похожих"],
  ["ограничения", "приборы, время, что уже пробовала и не сработало"],
  ["требования и примеры", "ГОСТы, похожие методики, «сделай как в приложенном файле»"],
  ["источники", "ссылки, если они у тебя есть"],
];
const changes = [
  ["Было", "Стало"],
  ["Выбирала модель, а правила писала в каждом запросе сама", "Наверху пять кнопок-сценариев: выбираешь задачу, модель и правила уже внутри"],
  ["Много моделей, часть похожи друг на друга", "Семь моделей. Убраны Sonnet, Kimi, DeepSeek, GLM и MiniMax: на проверках они ошибались, выдумывали или не справлялись с объёмом"],
  ["Непонятно, какая модель сильнее", "Все модели прогнали на одних и тех же научных задачах и на текстах до 200 страниц. Внутри полки сверху самая сильная"],
  ["Fable ставили на всё, на НИР он замолкал", "Теперь известно: Fable - только для правки текста до 40 страниц. Большое читают Astra Pro и Opus"],
  ["«Не додумывай» надо было помнить", "Это правило вшито в каждую кнопку"],
  ["Новые версии моделей появлялись без нас", "Раз в месяц новые версии проверяются. Если новая лучше, кнопка обновится, название и место в меню останутся"],
];
const CW = [4000, 5360];

const doc = new Document({
  creator: "poly-mind-infra",
  title: "Памятка: какую кнопку жать",
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  numbering: {
    config: [
      ...["steps", "rules"].map((reference) => ({
        reference,
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }],
      })),
      { reference: "dots", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { margin: { top: 1200, bottom: 1200, left: 1440, right: 1440 } } },
    children: [
      new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: "Памятка: какую кнопку жать", font: FONT })], spacing: { after: 120 } }),
      p("Главное изменение: думать о моделях больше не надо. Наверху меню пять кнопок, в каждую уже зашиты модель и порядок работы. Выбираешь задачу, а не модель."),

      h("Что изменилось в чате"),
      table([new TableRow({ tableHeader: true, children: changes[0].map((l, i) => cell(rich([[l, B]]), CW[i], { shading: { type: ShadingType.CLEAR, fill: "E7E6E6", color: "auto" } })) }), ...changes.slice(1).map((r) => row(r, CW))], CW),

      box("E2EFDA", "548235", [run("Правило ноль: не знаешь, что жать, - жми 🧭 Новый вопрос.", B), run(" Внутри Opus 5.5: он справился со всеми задачами на любой длине текста, ничего не выдумал и стоит центы. Сначала уточнит, что нужно, потом ответит.")]),
      box("DDEBF7", "2F5597", [run("Сомневаешься в кнопке - спроси ❓ Какую кнопку?", B), run(" Напиши задачу своими словами, например «надо проверить диплом студентки». Она ответит, что жать и что написать первой строкой. Стоит копейки.")]),
      box("F2F2F2", "7F7F7F", [run("«Не додумывай» писать больше не надо.", B), run(" Каждая кнопка начинает с правила: ничего не додумывай; не знаешь - так и скажи; непроверенное пометь; ссылок, чисел и названий не выдумывай.")]),

      h("1. Что хочу - что жму"),
      table([head(["Хочу", "Жму", "Что будет"], TW), ...tasks.map((r) => (r.length === 1 ? band(r[0], TW) : row(r, TW)))], TW),

      h("2. Сначала посмотри на размер текста"),
      p("Все аварии были из-за размера. Страница русского текста - примерно 700 токенов."),
      table([head(["Размер", "Что это", "Какие кнопки"], SW), ...sizes.map((r) => row(r, SW))], SW),
      box("FDECEA", "C00000", [run("Fable не отвечает на текстах длиннее 40–50 страниц.", B), run(" Он уходит в размышления и замолкает, а деньги списываются. Это проверено четыре раза, в том числе на твоей НИР. Кнопка ✏️ Править текст - тоже Fable, поэтому большой текст сама откажется брать и скажет, что делать.")]),

      h("3. Большой документ - в два шага"),
      item("steps", "Прочитать. ", "🧠 Astra Pro, один раз, с просьбой: «Прочитай целиком. Выпиши по разделам все числовые значения, главные утверждения и нестыковки. Не пересказывай». Через 20 секунд будет выжимка на 2–3 страницы. Стоит около доллара за 200 страниц."),
      item("steps", "Работать с выжимкой ", "любой кнопкой: ✏️ Править текст, 🎛 Варианты, 🧭 Новый вопрос. Выжимка маленькая, поэтому дёшево и без аварий."),
      p([run("Чтобы спросить «а что там сказано про…», прикладывай файл, а не вставляй текст. Чат сам найдёт нужный кусок, справится даже ⚡ Luna.")]),

      h("4. Второе мнение"),
      p([run("Всё, что идёт в статью, проверь второй раз: вывод, число, механизм. ", B), run("Скопируй ответ 🧭 Новый вопрос в 🔍 Рецензия. Там модель другой компании, а разные компании ошибаются по-разному. Если обе согласны - верь. Стоит центы и ловит выдумки.")]),

      h("5. Десять привычек для хороших запросов"),
      p([run("Главное правило - контекст. ", B), run("Хороший ответ даёт не хитрый запрос и не сильная модель, а полный контекст. Приложи всё, что вокруг вопроса:")]),
      ...context.map(([k, v]) => new Paragraph({ numbering: { reference: "dots", level: 0 }, spacing: { after: 40 }, children: [run(k, B), run(" - " + v)] })),
      p(""),
      p("Три привычки - всегда, семь - по случаю. Большую часть уже делают кнопки: справа написано, где это встроено и что остаётся на тебе."),
      table([head(["Привычка", "Кто делает", "Как"], HW), ...habits.map((r) => (r.length === 1 ? band(r[0], HW) : row(r, HW)))], HW),
      p(""),
      p([run("Без вежливости: ", B), run("«пожалуйста» и «будь добр» ничего не дают. "), run("Числа и ссылки из ответа проверяй сама.", B)]),

      h("6. Три правила, чтобы не платить лишнего"),
      item("rules", "Новый чат на каждую задачу. ", "Каждое сообщение в старом чате заново отправляет всю переписку. Длинный чат с Fable стоит 30–40 центов за каждое «а теперь ещё вот это»."),
      item("rules", "Мелочь - дешёвой кнопкой. ", "Быт, короткий абзац, черновик - ⚡ Luna, почти бесплатно. Дорогие кнопки - для важного."),
      item("rules", "Большой документ - только в два шага. ", "Fable на нём не ответит, а деньги возьмёт."),
      p([run("Дорогая привычка - не дорогая модель, а длинный чат. ", B), run("Для ориентира: статья через Grok стоит копейки, диплом через Astra Pro - около доллара, месяц обычной работы - 3–15 долларов.", GREY)]),

      new Paragraph({ children: [new PageBreak()] }),
      h("Меню сверху вниз"),
      p([run("Цена по-человечески: x0 почти бесплатно, x2–x5 копейки, x8 несколько центов за ответ, x20 до доллара на длинном тексте.", GREY)]),
      table([head(["Кнопка", "Цена", "Внутри / для чего"], MW), ...menu.map((r) => (r.length === 1 ? band(r[0], MW) : row(r, MW)))], MW),
    ],
  }],
});

const OUT = path.join(__dirname, "..", "docs", "памятка.docx");

async function parts(buf) {
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(buf);
  const out = {};
  for (const name of Object.keys(zip.files).sort()) {
    if (name !== "docProps/core.xml" && !zip.files[name].dir) out[name] = await zip.files[name].async("string");
  }
  return out;
}

async function main() {
  const buf = await Packer.toBuffer(doc);
  if (process.argv.includes("--check")) {
    if (!fs.existsSync(OUT)) { console.log("ERROR: docs/памятка.docx is missing - run node scripts/memo_docx.js"); process.exit(1); }
    const [want, have] = [await parts(buf), await parts(fs.readFileSync(OUT))];
    if (JSON.stringify(want) !== JSON.stringify(have)) {
      console.log("ERROR: docs/памятка.docx is not what scripts/memo_docx.js builds - run node scripts/memo_docx.js");
      process.exit(1);
    }
    console.log("ok: docs/памятка.docx matches scripts/memo_docx.js");
    return;
  }
  fs.writeFileSync(OUT, buf);
  console.log("wrote docs/памятка.docx", buf.length, "bytes");
}

main().catch((e) => { console.error(e); process.exit(1); });
