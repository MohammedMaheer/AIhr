// ASCII PDF with Helvetica and explicit content-stream order. No real CV data.
export function pdf(lines, pageCount = 1) {
  const stream = lines.map(([line, x, y]) => {
    const escaped = line.replace(/[\\()]/g, '\\$&');
    return `BT /F1 10 Tf 1 0 0 1 ${x} ${y} Tm (${escaped}) Tj ET\n`;
  }).join('');
  const pages = Array.from({ length: pageCount }, (_, i) => `${5 + i} 0 R`);
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    `<< /Type /Pages /Kids [${pages.join(' ')}] /Count ${pageCount} >>`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    ...pages.map(() => '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>'),
  ];
  let document = '%PDF-1.4\n';
  const offsets = [];
  for (const [i, object] of objects.entries()) {
    offsets.push(document.length);
    document += `${i + 1} 0 obj\n${object}\nendobj\n`;
  }
  return Buffer.from(document + `xref\n0 ${offsets.length + 1}\n0000000000 65535 f \n` +
    offsets.map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('') +
    `trailer\n<< /Size ${offsets.length + 1} /Root 1 0 R >>\nstartxref\n${document.length}\n%%EOF\n`, 'ascii');
}

const regular = lines => pdf(lines.map((line, i) => [line, 40, 740 - i * 16]));
const create = (id, role, city, years, skills, description) => ({
  id,
  bytes: regular([`Synthetic CV ${id}`, role, `Location: ${city}, UAE`,
    `Total experience: ${years} years`, `Skills: ${skills}`, 'Experience', description]),
});

export const corpus = [
  ...[
    'Built a React and Node.js marketplace with PostgreSQL.',
    'Maintained a React payments dashboard and Node.js services.',
    'Implemented Node.js authentication and React components.',
    'Delivered a React and Node.js booking app for logistics.',
    'Built accessible React interfaces and Node.js GraphQL APIs.',
    'Maintained React reporting widgets and Node.js data exports.',
    'Developed a Node.js scheduling service with a React UI.',
    'Used React hooks and Node.js for a subscription platform.',
    'Reworked a React storefront and optimized Node.js performance.',
    'Integrated third-party payments with React and Node.js.',
    'Built dashboards in React with Node.js and Redis caching.',
  ].map((description, i) => create(`dev-${i + 1}`, 'Full Stack Developer', 'Dubai', 2 + i % 3,
    'React, Node.js, JavaScript', description)),
  create('wrong-city', 'Full Stack Developer', 'Sharjah', 3, 'React, Node.js', 'Built enterprise web portals.'),
  create('wrong-years', 'Full Stack Developer', 'Dubai', 8, 'React, Node.js', 'Led web application delivery.'),
  create('design', 'Product Designer', 'Dubai', 5, 'Figma, prototyping', 'Created design systems and ran usability research.'),
  create('analyst', 'Data Analyst', 'Abu Dhabi', 5, 'Python, SQL, Tableau', 'Built reporting pipelines and developed demand forecasts.'),
  create('support', 'Technical Support Specialist', 'Dubai', 4, 'Active Directory, Jira', 'Managed incident triage and desktop troubleshooting.'),
  {
    id: 'two-column',
    bytes: pdf([
      ['Synthetic CV two-column', 40, 740],
      ['Data pipelines with Python, SQL and Tableau', 302, 706],
      ['Built demand forecasts and maintained BI dashboards', 302, 690],
      ['Data Analyst', 40, 706],
      ['Location: Abu Dhabi, UAE', 40, 690],
      ['Total experience: 6 years', 40, 674],
      ['Skills: Python, SQL, Tableau', 40, 658],
    ]),
  },
  { id: 'two-page', bytes: pdf([
    ['Synthetic CV two-page', 40, 740], ['Warehouse operations and stock control', 40, 720],
  ], 2) },
];

export const queries = [
  { name: 'ten-full-stack', limit: 10, text: 'Full Stack Developer based in Dubai with 2-4 years of experience. Required skills: React, Node.js.' },
  { name: 'designer', limit: 5, text: 'Product Designer based in Dubai with 4-6 years of experience. Required skills: Figma.' },
  { name: 'data-analyst', limit: 5, text: 'Data Analyst based in Abu Dhabi with 4-6 years of experience. Required skills: Python, SQL.' },
  { name: 'unmatched', limit: 10, text: 'Technical Support Specialist based in Ajman with 15-20 years of experience. Required skills: Kubernetes.' },
  { name: 'semantic-top-one', limit: 1, text: 'Demand forecasting and BI dashboards' },
  { name: 'semantic-top-ten', limit: 10, text: 'React payments dashboard and Node.js services' },
];

export const negatives = [
  { name: 'legacy.doc', bytes: Buffer.from('synthetic'), expected: 'unsupported-type' },
  { name: 'word.docx', bytes: Buffer.from('synthetic'), expected: 'unsupported-type' },
  { name: 'empty.pdf', bytes: Buffer.alloc(0), expected: 'file-size' },
  { name: 'oversized.pdf', bytes: Buffer.alloc(10 * 1024 * 1024 + 1), expected: 'file-size' },
  { name: 'broken.pdf', bytes: Buffer.from('invalid PDF'), expected: 'pdf-unavailable' },
  { name: 'no-text.pdf', bytes: pdf([]), expected: 'insufficient-text' },
  { name: 'too-many-pages.pdf', bytes: pdf([], 21), expected: 'page-limit' },
];
