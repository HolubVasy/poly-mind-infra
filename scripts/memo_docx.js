// Builds docs/памятка.docx - the Word памятка the mother keeps - from
// docs/памятка.md, the one source of truth. Edit the .md, never the .docx:
// the helper «❓ Какую кнопку?» reads the same .md, and build_presets.py
// regenerates its menu table (models and prices) from models/slots.yaml.
//
// Understands the Markdown the памятка uses, nothing more:
//   # title, ## heading, ### subheading, paragraphs, **bold**, `code`,
//   [text](url), "- " bullets, "1. " numbered lists, tables (a row whose
//   cells after the first are empty is a group band), GitHub alerts
//   (> [!TIP] / [!NOTE] / [!IMPORTANT] / [!WARNING] / [!CAUTION]) as coloured
//   boxes, <!-- pagebreak --> and other one-line comments (ignored).
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

const ROOT = path.join(__dirname, "..");
const MD = path.join(ROOT, "docs", "памятка.md");
const OUT = path.join(ROOT, "docs", "памятка.docx");
const FONT = "Calibri";
const PAGE_WIDTH = 9360; // A4 minus 2.54 cm margins, DXA
const BOXES = {
  TIP: ["E2EFDA", "548235"],
  NOTE: ["DDEBF7", "2F5597"],
  IMPORTANT: ["F2F2F2", "7F7F7F"],
  WARNING: ["FFF2CC", "BF8F00"],
  CAUTION: ["FDECEA", "C00000"],
};

function inline(text, base = {}) {
  const runs = [];
  for (const part of text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/)) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**")) runs.push(new TextRun({ text: part.slice(2, -2), font: FONT, size: 22, ...base, bold: true }));
    else if (part.startsWith("`") && part.endsWith("`")) runs.push(new TextRun({ text: part.slice(1, -1), font: "Consolas", size: 20, ...base }));
    else if (part.startsWith("[")) runs.push(new TextRun({ text: part.replace(/^\[([^\]]+)\].*$/, "$1"), font: FONT, size: 22, ...base }));
    else runs.push(new TextRun({ text: part, font: FONT, size: 22, ...base }));
  }
  return runs;
}

const para = (text, opts = {}) => new Paragraph({ children: inline(text), spacing: { after: 120 }, ...opts });

function cells(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

function widths(rows) {
  const n = rows[0].length;
  const weight = [];
  for (let i = 0; i < n; i++) {
    const lens = rows.map((r) => (r[i] || "").replace(/\*\*/g, "").length).filter((l) => l > 0);
    const avg = lens.length ? lens.reduce((a, b) => a + b, 0) / lens.length : 8;
    weight.push(Math.min(Math.max(avg, 16), 70));
  }
  const sum = weight.reduce((a, b) => a + b, 0);
  const w = weight.map((x) => Math.round((x / sum) * PAGE_WIDTH));
  w[n - 1] += PAGE_WIDTH - w.reduce((a, b) => a + b, 0);
  return w;
}

function cell(text, width, opts = {}, runBase = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: inline(text, runBase), spacing: { after: 0 } })],
    ...opts,
  });
}

function table(lines) {
  const rows = lines.filter((l, i) => i !== 1).map(cells);
  const w = widths(rows);
  const total = w.reduce((a, b) => a + b, 0);
  const grey = (fill) => ({ shading: { type: ShadingType.CLEAR, fill, color: "auto" } });
  const out = [new TableRow({ tableHeader: true, children: rows[0].map((c, i) => cell(`**${c.replace(/\*\*/g, "")}**`, w[i], grey("E7E6E6"))) })];
  for (const r of rows.slice(1)) {
    if (r.slice(1).every((c) => !c)) {
      out.push(new TableRow({ children: [cell(`**${r[0].replace(/\*\*/g, "")}**`, total, { columnSpan: w.length, ...grey("F2F2F2") }, { color: "404040" })] }));
    } else {
      out.push(new TableRow({ children: w.map((width, i) => cell(r[i] || "", width)) }));
    }
  }
  return new Table({ columnWidths: w, width: { size: total, type: WidthType.DXA }, rows: out });
}

function box(lines) {
  let kind = "NOTE";
  const body = lines.map((l) => l.replace(/^>\s?/, ""));
  const m = /^\[!(\w+)\]\s*$/.exec(body[0] || "");
  if (m && BOXES[m[1]]) { kind = m[1]; body.shift(); }
  const [fill, line] = BOXES[kind];
  const paras = body.join("\n").split(/\n\s*\n/).map((p) => p.replace(/\n/g, " ").trim()).filter(Boolean);
  return paras.map((p) => new Paragraph({
    children: inline(p),
    spacing: { before: 60, after: 120 },
    shading: { type: ShadingType.CLEAR, fill, color: "auto" },
    border: { left: { style: BorderStyle.SINGLE, size: 24, color: line, space: 8 } },
  }));
}

function convert(md) {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let title = "";
  let lists = 0;
  let i = 0;
  const take = (re) => { const got = []; while (i < lines.length && re.test(lines[i])) got.push(lines[i++]); return got; };
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) { i++; continue; }
    if (/^<!--\s*pagebreak\s*-->/.test(l)) { out.push(new Paragraph({ children: [new PageBreak()] })); i++; continue; }
    if (/^<!--.*-->\s*$/.test(l)) { i++; continue; }
    let m;
    if ((m = /^# (.*)$/.exec(l))) {
      title = m[1];
      out.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: m[1], font: FONT })], spacing: { after: 120 } }));
      i++; continue;
    }
    if ((m = /^(##|###) (.*)$/.exec(l))) {
      out.push(new Paragraph({ heading: m[1] === "##" ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2, children: [new TextRun({ text: m[2], font: FONT })], spacing: { before: 280, after: 120 } }));
      i++; continue;
    }
    if (l.startsWith(">")) { out.push(...box(take(/^>/))); continue; }
    if (l.startsWith("|")) { out.push(table(take(/^\|/)), para("")); continue; }
    if (/^\d+\. /.test(l)) {
      lists += 1;
      for (const item of take(/^\d+\. /)) {
        out.push(new Paragraph({ numbering: { reference: "numbers", level: 0, instance: lists }, spacing: { after: 100 }, children: inline(item.replace(/^\d+\.\s+/, "")) }));
      }
      continue;
    }
    if (/^[-*] /.test(l)) {
      for (const item of take(/^[-*] /)) {
        out.push(new Paragraph({ numbering: { reference: "dots", level: 0 }, spacing: { after: 40 }, children: inline(item.replace(/^[-*]\s+/, "")) }));
      }
      out.push(para(""));
      continue;
    }
    const block = take(/^(?!\s*$)(?!#)(?!>)(?!\|)(?!\d+\. )(?![-*] )(?!<!--)/);
    out.push(para(block.join(" ").trim()));
  }
  return { title, children: out };
}

function build() {
  const { title, children } = convert(fs.readFileSync(MD, "utf8"));
  const indent = { paragraph: { indent: { left: 540, hanging: 360 } } };
  return new Document({
    creator: "poly-mind-infra",
    title,
    styles: { default: { document: { run: { font: FONT, size: 22 } } } },
    numbering: {
      config: [
        { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: indent }] },
        { reference: "dots", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: indent }] },
      ],
    },
    sections: [{ properties: { page: { margin: { top: 1200, bottom: 1200, left: 1440, right: 1440 } } }, children }],
  });
}

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
  const buf = await Packer.toBuffer(build());
  if (process.argv.includes("--check")) {
    if (!fs.existsSync(OUT)) { console.log("ERROR: docs/памятка.docx is missing - run node scripts/memo_docx.js"); process.exit(1); }
    const [want, have] = [await parts(buf), await parts(fs.readFileSync(OUT))];
    if (JSON.stringify(want) !== JSON.stringify(have)) {
      console.log("ERROR: docs/памятка.docx is not what scripts/memo_docx.js builds from docs/памятка.md - run node scripts/memo_docx.js");
      process.exit(1);
    }
    console.log("ok: docs/памятка.docx matches docs/памятка.md");
    return;
  }
  fs.writeFileSync(OUT, buf);
  console.log("wrote docs/памятка.docx", buf.length, "bytes");
}

main().catch((e) => { console.error(e); process.exit(1); });
