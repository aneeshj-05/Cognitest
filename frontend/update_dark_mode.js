const fs = require('fs');
const files = [
  'src/components/landing/HeroSection.tsx',
  'src/components/landing/DemoSection.tsx',
  'src/components/landing/ProblemSolutionSection.tsx',
  'src/components/landing/CapabilitiesSection.tsx',
  'src/components/landing/TrustSection.tsx',
  'src/components/landing/Navbar.tsx',
  'src/pages/public/LandingPage.tsx'
];

files.forEach(f => {
  if(!fs.existsSync(f)) return;
  let c = fs.readFileSync(f, 'utf8');
  
  // Apply dark mode classes
  c = c.replace(/text-zinc-900(?! dark:text-zinc-100)/g, 'text-zinc-900 dark:text-zinc-100');
  c = c.replace(/text-zinc-800(?! dark:text-zinc-200)/g, 'text-zinc-800 dark:text-zinc-200');
  c = c.replace(/text-zinc-500(?! dark:text-zinc-400)/g, 'text-zinc-500 dark:text-zinc-400');
  c = c.replace(/text-zinc-400(?! dark:text-zinc-500)/g, 'text-zinc-400 dark:text-zinc-500');
  c = c.replace(/bg-white(?! dark:bg-zinc-[0-9]+)/g, 'bg-white dark:bg-zinc-950');
  c = c.replace(/border-zinc-200(?! dark:border-zinc-800)/g, 'border-zinc-200 dark:border-zinc-800');
  c = c.replace(/border-zinc-100(?! dark:border-zinc-800)/g, 'border-zinc-100 dark:border-zinc-800');
  c = c.replace(/bg-zinc-50\/50(?! dark:bg-zinc-900\/50)/g, 'bg-zinc-50/50 dark:bg-zinc-900/50');
  c = c.replace(/bg-zinc-50\/30(?! dark:bg-zinc-900\/30)/g, 'bg-zinc-50/30 dark:bg-zinc-900/30');
  c = c.replace(/bg-zinc-50(?![\/\w])(?! dark:bg-zinc-900)/g, 'bg-zinc-50 dark:bg-zinc-900');
  
  // Fix typography (very important fix)
  c = c.replace(/font-extrabold/g, 'font-semibold');
  c = c.replace(/font-black/g, 'font-semibold');
  c = c.replace(/font-bold/g, 'font-semibold');

  fs.writeFileSync(f, c);
  console.log('Updated ' + f);
});
