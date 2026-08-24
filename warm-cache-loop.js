const { exec } = require("child_process");

const URL = "http://eaziline.com/";
const INTERVAL = 30 * 1000;
const TERMINAL_COUNT = 20;

function closeTerminals() {
    console.log("Closing previous Terminal windows...");

    exec(`
        osascript -e '
        tell application "Terminal"
            repeat with w in windows
                try
                    close w
                end try
            end repeat
        end tell'
    `);
}

function run() {
    // Close previous Terminal windows
    closeTerminals();

    // Give Terminal a moment to close
    setTimeout(() => {
        console.log(`Opening ${TERMINAL_COUNT} Terminal windows...`);

        for (let i = 0; i < TERMINAL_COUNT; i++) {
            exec(`
                osascript -e '
                tell application "Terminal"
                    activate
                    do script "cd \\"${process.cwd()}\\" && python3 warm-cache.py ${URL}"
                end tell'
            `);
        }
    }, 1000);
}

// Run immediately
run();

// Repeat every 30 seconds
setInterval(run, INTERVAL);