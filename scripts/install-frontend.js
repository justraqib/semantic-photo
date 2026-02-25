import { execSync } from 'child_process';
import { readdirSync } from 'fs';

// Debug: find where the project lives
console.log('CWD:', process.cwd());
try {
  console.log('Home contents:', readdirSync('/home/user').join(', '));
} catch(e) { console.log('No /home/user'); }
try {
  console.log('/vercel contents:', readdirSync('/vercel').join(', '));
} catch(e) { console.log('No /vercel'); }
try {
  console.log('/vercel/share contents:', readdirSync('/vercel/share').join(', '));
} catch(e) { console.log('No /vercel/share'); }

// Try to find package.json
const result = execSync('find / -name "package.json" -path "*/frontend/*" -maxdepth 5 2>/dev/null || true').toString();
console.log('Found package.json files:', result);
