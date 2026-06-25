const fs = require('fs');
const { PDFParse } = require('pdf-parse');

const dataBuffer = fs.readFileSync('c:/Users/Farhad/Documents/anything/problem.pdf');

(async () => {
    try {
        const parser = new PDFParse({ data: dataBuffer });
        await parser.load();
        const result = await parser.getText();
        // result shape: { text, totalPages, pages: [{ pageNumber, text, ...}] }
        if (result && typeof result.text === 'string' && result.text.length > 0) {
            process.stdout.write(result.text);
        } else if (result && Array.isArray(result.pages)) {
            const out = result.pages.map(p => `=== PAGE ${p.pageNumber} ===\n${p.text || ''}`).join('\n\n');
            process.stdout.write(out);
        } else {
            console.error('Unexpected result shape:', JSON.stringify(result).slice(0, 500));
            process.exit(2);
        }
    } catch (err) {
        console.error('ERROR:', err && err.stack ? err.stack : err);
        process.exit(1);
    }
})();
