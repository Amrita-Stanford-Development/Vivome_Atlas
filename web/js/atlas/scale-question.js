// The question the Atlas page asks about a protein file's values, as the
// file is chosen: are they raw intensities, or already log, and with Already
// log, what a 0 means (research/value-scale-b5-design.md, "The pop-up").
// Pure: what to ask, the file's line, and what the Values and Zeros menus
// are set to; data-tab.js opens the dialog. Nothing here reads the numbers:
// the page shows the file's own facts and leaves the reading to the
// uploader, or to the service's check when they don't know.

import { formatCount } from '../manifest.js';

const READINGS = ['linear', 'log', 'auto'];
const ZEROS = ['missing', 'measured', 'auto'];

// Asked of a protein file whose check passed. A check overtaken by another
// file comes back null (landing.js, chooseFile), so only the latest asks.
export function asksScale({ modality, check } = {}) {
  return modality === 'prot' && check?.ok === true;
}

// What a 0 means is asked only of a file that has one.
export function asksZeros(check) {
  return check?.values?.zeros > 0;
}

// The menus' values for the answers: an unknown reading is I don't know,
// and what a 0 means is kept only with Already log.
export function menuChoice(reading, zeros = 'auto') {
  const valueScale = READINGS.includes(reading) ? reading : 'auto';
  return { valueScale, zeros: valueScale === 'log' && ZEROS.includes(zeros) ? zeros : 'auto' };
}

// The file as its check found it: its name, feature rows and cells.
export function questionFile(check) {
  const many = (n, word) => `${formatCount(n)} ${word}${n === 1 ? '' : 's'}`;
  return `${check?.name ?? 'Your file'}: ${many(check?.features, 'feature row')}, ${many(check?.cells, 'cell')}`;
}
