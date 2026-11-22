/**
 * Room checks for the Maze Rooms sheet. Paste this whole file into Extensions > Apps Script.
 *
 * It runs the same checks as maze2/rooms/rooms.py (keep the two in sync) and writes each room's
 * problems into its Errors cell. A conditional format turns the room's Structure Name red when its
 * Errors cell isn't empty. Problems that don't belong to one room go in a note on the Errors header
 * and a popup.
 *
 * It runs after every edit on the Chart tab, and from the Maze > Check rooms menu.
 * Rooms with Ignore checked are skipped entirely, as if they weren't there. Disabled is only checked
 * for being a TRUE/FALSE box: it decides which lookups start without the enabled tag, not whether they build.
 */

const TAB = "Chart";
const ERRORS_HEADER = "Errors";

// keep in sync with rooms.py
const SIDES = ["north", "east", "south", "west", "up", "down"];
const HORIZONTAL_SIDES = SIDES.slice(0, 4);
const ROTATING_SIDES = ["up", "down"];
const OPPOSITE = { up: "down", down: "up" };
const HORIZONTAL = "horizontal", VERTICAL = "up/down";
const CONSTRAINT = "constraint";
const CONSTRAINT_ID = 0;
const INNER_FIRST_ID = 1001;
const TARGET_AMOUNT = 6;
const MIN_WEIGHT = -100, MAX_WEIGHT = 100;
const ROTATIONS = 4;
const VARIANT_SUFFIX = "_R";
const ENCODING_RE = /^[^\s(),]+$/;
const CATEGORY_RE = /^[A-Za-z0-9_.+-]+$/;
const STRUCTURE_RE = /^([a-z0-9_.-]+:)?[a-z0-9_./-]+$/;

// ------------------------------------------------------------------------------ Apps Script glue

function onOpen() {
  SpreadsheetApp.getUi().createMenu("Maze").addItem("Check rooms", "checkRoomsFromMenu").addToUi();
}

function onEdit(e) {
  if (e && e.range && e.range.getSheet().getName() === TAB) checkRooms(false);
}

function checkRoomsFromMenu() {
  checkRooms(true);
}

function checkRooms(fromMenu) {
  const spreadsheet = SpreadsheetApp.getActive();
  const sheet = spreadsheet.getSheetByName(TAB);
  const rows = sheet.getDataRange().getDisplayValues();
  const column = rows[0].map(cell => cell.trim().toLowerCase()).indexOf(ERRORS_HEADER.toLowerCase());
  if (column < 0) {
    spreadsheet.toast(`Add a column with the header "${ERRORS_HEADER}" first.`, "Room checks", 10);
    return;
  }
  const result = checkSheet(rows);
  if (rows.length > 1) {
    sheet.getRange(2, column + 1, rows.length - 1, 1).setValues(result.rowErrors.slice(1).map(lines => [lines.join("\n")]));
  }
  const header = sheet.getRange(1, column + 1);
  header.setNote(result.globalErrors.join("\n"));

  const count = result.rowErrors.reduce((n, lines) => n + lines.length, 0) + result.globalErrors.length;
  const summary = count === 0 ? "No errors." : `${count} error(s). See the ${ERRORS_HEADER} column.`;
  if (result.globalErrors.length) {
    const text = `${summary}\n\nNot tied to one room:\n${result.globalErrors.join("\n")}`;
    if (fromMenu) SpreadsheetApp.getUi().alert("Room checks", text, SpreadsheetApp.getUi().ButtonSet.OK);
    else spreadsheet.toast(text, "Room checks", 15);
  } else if (fromMenu) {
    spreadsheet.toast(summary, "Room checks", 5);
  }
}

// ------------------------------------------------------------------------------------- the checks

/**
 * rows: the sheet's displayed values, header row first. Returns rowErrors (one list of messages per
 * row, same indexes as rows) and globalErrors (problems not tied to one room).
 */
function checkSheet(rows) {
  const rowErrors = rows.map(() => []);
  const globalErrors = [];
  const header = rows[0].map(cell => String(cell).trim().toLowerCase());
  const cell = (row, i) => (i < row.length ? String(row[i]).trim() : "");

  // columns, found by header like rooms.py's convert_sheet
  const layout = [];
  const find = name => {
    const matches = header.flatMap((h, i) => (h === name.toLowerCase() ? [i] : []));
    if (matches.length !== 1) layout.push(`expected one '${name}' column in the header, found ${matches.length}`);
    return matches[0];
  };
  const after = (column, offset, name) => {
    if (column === undefined || header[column + offset] !== name.toLowerCase()) {
      layout.push(`expected '${name}' ${offset} column(s) after '${rows[0][column]}' in the header`);
    }
    return column + offset;
  };
  const col = { name: find("Structure Name"), weight: find("Room Weight"), categories: find("Categories"), ignore: find("Ignore"),
    disabled: find("Disabled") };
  col.sides = SIDES.map(side => find(side[0].toUpperCase() + side.slice(1)));
  col.inner = col.sides.map(c => after(c, 1, "In?"));
  col.rot = ROTATING_SIDES.map(side => after(col.sides[SIDES.indexOf(side)], 2, "Rot?"));
  const width = Math.max(...rows.map(row => row.length));
  const markers = [];
  for (let i = 0; i < width; i++) if (rows.slice(1).some(row => cell(row, i) === "This")) markers.push(i);
  if (markers.length !== 1) layout.push(`expected one column with 'This' rows in it, found ${markers.length}`);
  if (layout.length) return { rowErrors, globalErrors: layout };

  const kind = i => (i > 0 && i < rows.length ? cell(rows[i], markers[0]) : "");
  const flag = value => ({ "": false, FALSE: false, TRUE: true })[value.toUpperCase()];

  // read the rooms (rooms.py: convert_sheet, then parse_rooms)
  const rooms = [];
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const error = message => rowErrors[i].push(message);
    if (kind(i) === "Target") {
      if (kind(i - 1) !== "This") error("a Target row has to be right under a This row");
      continue;
    }
    if (kind(i) !== "This") {
      if ([col.weight, col.categories, col.name, ...col.sides].some(c => cell(row, c))) {
        error("has data but isn't marked This or Target");
      }
      continue;
    }
    if (kind(i + 1) !== "Target") error("a This row needs a Target row right under it");
    const ignored = flag(cell(row, col.ignore));
    if (ignored === undefined) error(`Ignore is '${cell(row, col.ignore)}', it must be TRUE, FALSE or blank`);
    if (ignored) continue;

    const target = kind(i + 1) === "Target" ? rows[i + 1] : [];
    const name = cell(row, col.name);
    const sides = col.sides.map(c => cell(row, c));
    const targetCells = col.sides.map(c => cell(target, c));
    if (!name && !cell(row, col.categories) && !sides.some(Boolean) && !targetCells.some(Boolean)) continue;

    if (!name) error("missing structure name");
    else if (!STRUCTURE_RE.test(name)) error(`structure name '${name}' isn't a valid resource location (lowercase a-z, 0-9, _ . - / only)`);

    const weightText = cell(row, col.weight);
    if (weightText) {
      const value = Number(weightText);
      if (!Number.isInteger(value) || value < MIN_WEIGHT || value > MAX_WEIGHT) {
        error(`room weight '${weightText}' must be a whole number from ${MIN_WEIGHT} to ${MAX_WEIGHT}`);
      }
    }
    for (const category of parseList(cell(row, col.categories))) {
      if (!CATEGORY_RE.test(category)) error(`category '${category}' can only use letters, digits and _ . + -`);
    }
    SIDES.forEach((side, d) => {
      if (!sides[d]) error(`missing ${side} encoding`);
      else if (!ENCODING_RE.test(sides[d])) error(`${side} encoding '${sides[d]}' must be one encoding with no spaces, commas or brackets`);
    });
    const box = (label, side, value) => {
      const parsed = flag(value);
      if (parsed === undefined) error(`${label} ${side} is '${value}', it must be TRUE, FALSE or blank`);
      return Boolean(parsed);
    };
    const inner = SIDES.map((side, d) => box("In", side, cell(row, col.inner[d])));
    if (flag(cell(row, col.disabled)) === undefined) {
      error(`Disabled is '${cell(row, col.disabled)}', it must be TRUE, FALSE or blank`);
    }
    const rot = SIDES.map(() => false);
    ROTATING_SIDES.forEach((side, k) => (rot[SIDES.indexOf(side)] = box("Rot", side, cell(row, col.rot[k]))));
    const targets = SIDES.map((side, d) => {
      const items = [...new Set(parseList(targetCells[d]))];
      if (!items.length) error(`${side} target list is empty`);
      else if (items.length > TARGET_AMOUNT) error(`${side} target list has ${items.length} encodings, the most is ${TARGET_AMOUNT}`);
      for (const item of items) {
        if (!item) error(`${side} target list has an empty entry (extra comma?)`);
        else if (!ENCODING_RE.test(item)) error(`${side} target '${item}' must be one encoding with no spaces, commas or brackets`);
      }
      return items;
    });
    rooms.push({ index: i, row: i + 1, name, sides, targets, inner, rot });
  }
  const roomError = (room, message) => rowErrors[room.index].push(message);

  // In and Rot agree for each encoding on its axis (rooms.py: check_flags)
  const first = new Map();
  const reported = new Set();
  let flagErrors = 0;
  for (const room of rooms) {
    SIDES.forEach((side, d) => {
      const encoding = room.sides[d], isInner = room.inner[d], rotates = room.rot[d];
      if (!encoding) return;
      if (encoding === CONSTRAINT) {
        if (isInner || rotates) {
          roomError(room, `${side} is ${CONSTRAINT}, which can't be In or Rot (it's always id ${CONSTRAINT_ID})`);
          flagErrors++;
        }
        return;
      }
      const key = `${axis(side)}|${encoding}`;
      if (!first.has(key)) {
        first.set(key, { room, side, isInner, rotates });
        return;
      }
      const was = first.get(key);
      const where = `on ${was.side} in row ${was.room.row} (${was.room.name})`;
      if (isInner !== was.isInner && !reported.has(key + "|In")) {
        reported.add(key + "|In");
        flagErrors++;
        roomError(room, `${side} encoding '${encoding}' has In ${isInner ? "checked" : "unchecked"}, but ${where} it's ` +
          `${was.isInner ? "checked" : "unchecked"}. Every ${axis(side)} side has to check In the same way for it`);
      }
      if (rotates !== was.rotates && !reported.has(key + "|Rot")) {
        reported.add(key + "|Rot");
        flagErrors++;
        roomError(room, `${side} encoding '${encoding}' ${rotates ? "rotates" : "does not rotate"}, but ${where} it ` +
          `${was.rotates ? "does" : "does not"}. Give the rotating one its own name`);
      }
    });
  }
  if (!flagErrors) {
    const own = encodingUses(rooms, false);
    const inIds = new Set(own.filter(u => u.isInner).map(u => u.encoding));
    const split = [...new Set(own.filter(u => !u.isInner && inIds.has(u.encoding)).map(u => u.encoding))].sort();
    for (const encoding of split) {
      globalErrors.push(`encoding '${encoding}' has In checked on one axis but not the other. Since it doesn't rotate ` +
        `on up and down, both axes share one id, so give one of them its own name`);
    }
  }

  // every target is some room's own encoding, on a side it can face (rooms.py: parse_rooms, unmatched_targets)
  const ownOn = Object.fromEntries(SIDES.map(side => [side, new Set()]));
  for (const room of rooms) SIDES.forEach((side, d) => ownOn[side].add(room.sides[d]));
  const anywhere = new Set(SIDES.flatMap(side => [...ownOn[side]]));
  const known = new Set([CONSTRAINT, ...anywhere]);
  for (const room of rooms) {
    SIDES.forEach((side, d) => {
      for (const item of room.targets[d]) {
        if (item && !known.has(item)) roomError(room, `${side} target '${item}' isn't any room's own encoding`);
      }
    });
  }
  for (const room of rooms) {
    SIDES.forEach((side, d) => {
      const need = HORIZONTAL_SIDES.includes(side) ? HORIZONTAL_SIDES : [OPPOSITE[side]];
      for (const item of room.targets[d]) {
        if (item && item !== CONSTRAINT && anywhere.has(item) && !need.some(s => ownOn[s].has(item))) {
          const where = HORIZONTAL_SIDES.includes(side) ? "any horizontal side" : OPPOSITE[side];
          roomError(room, `${side} target '${item}' is no room's own encoding on ${where}, so it can never match`);
        }
      }
    });
  }

  // id ranges (rooms.py: parse_rooms)
  const { rotating } = encodingFlags(rooms);
  for (const encoding of [...rotating].sort()) {
    for (const name of variants(encoding, "up", rotating)) {
      if (known.has(name)) globalErrors.push(`encoding '${name}' has the same name as a variant of the rotating encoding '${encoding}'`);
    }
  }
  const plain = new Set(encodingUses(rooms, true).filter(u => !u.isInner && u.base !== CONSTRAINT).map(u => u.encoding));
  const most = INNER_FIRST_ID - CONSTRAINT_ID - 1;
  if (plain.size > most) globalErrors.push(`${plain.size} encodings without In, the most is ${most} (In encodings start at ${INNER_FIRST_ID})`);
  if (!rooms.length && !globalErrors.length) globalErrors.push("no rooms found below the header row");
  return { rowErrors, globalErrors };
}

function axis(side) {
  return HORIZONTAL_SIDES.includes(side) ? HORIZONTAL : VERTICAL;
}

/** `(open, close)` or `open, close` or `open` -> ["open", "close"]. Keeps empty entries for errors. */
function parseList(text) {
  text = text.trim();
  if (text.startsWith("(") && text.endsWith(")")) text = text.slice(1, -1);
  if (!text.trim()) return [];
  return text.split(",").map(item => item.trim());
}

/** In encodings per axis and the rotating encodings, from each encoding's first own use on its axis. */
function encodingFlags(rooms) {
  const inner = { [HORIZONTAL]: new Set(), [VERTICAL]: new Set() };
  const rotating = new Set();
  const seen = new Set();
  for (const room of rooms) {
    SIDES.forEach((side, d) => {
      const key = `${axis(side)}|${room.sides[d]}`;
      if (seen.has(key)) return;
      seen.add(key);
      if (room.inner[d]) inner[axis(side)].add(room.sides[d]);
      if (room.rot[d]) rotating.add(room.sides[d]);
    });
  }
  return { inner, rotating };
}

function variants(encoding, side, rotating) {
  if (axis(side) !== VERTICAL || !rotating.has(encoding)) return [encoding];
  return Array.from({ length: ROTATIONS }, (_, turns) => `${encoding}${VARIANT_SUFFIX}${90 * turns}`);
}

/** Every use of an encoding in the lookups: sides, then targets unless `targets` is false. */
function encodingUses(rooms, targets) {
  const { inner, rotating } = encodingFlags(rooms);
  const uses = [];
  for (const room of rooms) {
    const sided = SIDES.map((side, d) => [side, room.sides[d]]);
    if (targets) SIDES.forEach((side, d) => room.targets[d].forEach(item => sided.push([side, item])));
    for (const [side, base] of sided) {
      for (const encoding of variants(base, side, rotating)) {
        uses.push({ encoding, base, isInner: inner[axis(side)].has(base) });
      }
    }
  }
  return uses;
}

if (typeof module !== "undefined") module.exports = { checkSheet };
