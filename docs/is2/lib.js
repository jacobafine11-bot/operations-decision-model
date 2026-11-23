// lib.js — shared building blocks for the Independent Study 2 documents.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  ShadingType, AlignmentType, HeadingLevel, LevelFormat, Footer, PageNumber,
  BorderStyle, PageBreak, TableLayoutType,
} = require("docx");

const FONT = "Arial";
const INK = "1A1A1A", INK2 = "52514E", ACCENT = "2A78D6", RULE = "D9D8D4", HEAD_FILL = "EEF3FA";
const CONTENT_W = 9360; // US Letter, 1-inch margins

// **bold** markup inside a string -> TextRuns
function runs(text, opts = {}) {
  const parts = String(text).split("**");
  return parts.map((t, i) => new TextRun({ text: t, bold: i % 2 === 1 || opts.bold, italics: opts.italics,
    color: opts.color || INK, size: opts.size, font: FONT }));
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text, opts), spacing: { after: opts.after ?? 120, line: 276 },
  alignment: opts.align });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: t, font: FONT })] });
const bullet = (t, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(t),
  spacing: { after: 60, line: 276 } });
const num = (t, ref = "numbers") => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t),
  spacing: { after: 60, line: 276 } });
const note = (t) => new Paragraph({ children: runs(t, { color: INK2, size: 19, italics: true }), spacing: { after: 160 } });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });
const rule = () => new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 1 } },
  spacing: { after: 160 } });

function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  if (Math.abs(total - CONTENT_W) > 2) throw new Error(`table widths sum ${total}, expected ${CONTENT_W}`);
  const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, w, head) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: HEAD_FILL } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: runs(text, { bold: head, size: 19 }), spacing: { after: 0, line: 252 } })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths, layout: TableLayoutType.FIXED,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], true)) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], false)) }))],
  });
}
const gap = () => new Paragraph({ children: [], spacing: { after: 80 } });

function build(path, title, children) {
  const doc = new Document({
    creator: "Jacob Fine", title,
    styles: {
      default: { document: { run: { font: FONT, size: 22, color: INK } } },
      paragraphStyles: [
        { id: "Title", name: "Title", basedOn: "Normal", run: { font: FONT, size: 44, bold: true, color: INK },
          paragraph: { spacing: { before: 0, after: 120 }, keepNext: true } },
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT, size: 30, bold: true, color: INK }, paragraph: { spacing: { before: 360, after: 140 }, keepNext: true, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT, size: 24, bold: true, color: ACCENT }, paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { font: FONT, size: 22, bold: true, color: INK }, paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 2 } },
      ],
    },
    numbering: { config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
        { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
      ...["numbers", "numbers2", "numbers3", "numbers4"].map((r) => ({ reference: r, levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })),
    ] },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new TextRun({ text: title + "  ·  page ", font: FONT, size: 16, color: INK2 }),
        new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: INK2 })] })] }) },
      children,
    }],
  });
  return Packer.toBuffer(doc).then((b) => fs.writeFileSync(path, b));
}

module.exports = { P, H1, H2, H3, bullet, num, note, table, pageBreak, rule, gap, build, runs, CONTENT_W, Paragraph, TextRun };
