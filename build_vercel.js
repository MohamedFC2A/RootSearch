const fs = require('fs');
const path = require('path');

const cwd = process.cwd();
console.log('[Vercel Build] Current Working Directory:', cwd);

let webDir = cwd;
if (fs.existsSync(path.join(cwd, 'web', 'templates'))) {
    webDir = path.join(cwd, 'web');
} else if (fs.existsSync(path.join(cwd, 'templates'))) {
    webDir = cwd;
} else if (fs.existsSync(path.join(cwd, '..', 'web', 'templates'))) {
    webDir = path.join(cwd, '..', 'web');
} else {
    console.error('[Vercel Build] Error: Neither web/templates nor templates directory found!');
    process.exit(1);
}

const templatesDir = path.join(webDir, 'templates');
const staticDir = path.join(webDir, 'static');
const publicDir = path.join(cwd, 'public');
const publicStaticDir = path.join(publicDir, 'static');

console.log('[Vercel Build] Templates Dir:', templatesDir);
console.log('[Vercel Build] Static Dir:', staticDir);

function copyFolderRecursiveSync(source, target) {
    if (!fs.existsSync(target)) {
        fs.mkdirSync(target, { recursive: true });
    }

    if (fs.lstatSync(source).isDirectory()) {
        const files = fs.readdirSync(source);
        files.forEach((file) => {
            const curSource = path.join(source, file);
            const curTarget = path.join(target, file);
            if (fs.lstatSync(curSource).isDirectory()) {
                copyFolderRecursiveSync(curSource, curTarget);
            } else {
                fs.copyFileSync(curSource, curTarget);
            }
        });
    }
}

fs.mkdirSync(publicStaticDir, { recursive: true });

if (fs.existsSync(templatesDir)) {
    const htmlFiles = fs.readdirSync(templatesDir).filter(f => f.endsWith('.html'));
    console.log('[Vercel Build] Copying HTML templates:', htmlFiles);
    htmlFiles.forEach(file => {
        fs.copyFileSync(path.join(templatesDir, file), path.join(publicDir, file));
    });
} else {
    console.error('[Vercel Build] Error: Templates directory does not exist:', templatesDir);
    process.exit(1);
}

if (fs.existsSync(staticDir)) {
    console.log('[Vercel Build] Copying static assets to public/static...');
    copyFolderRecursiveSync(staticDir, publicStaticDir);
} else {
    console.warn('[Vercel Build] Warning: Static directory not found at:', staticDir);
}

console.log('[Vercel Build] Build completed successfully!');
