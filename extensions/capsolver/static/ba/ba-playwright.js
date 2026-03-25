/*
    Steps to integrate Captcha Solver into your Puppeteer project.
    Step 1.
    Download the Captcha Solver extension and save it to your project.

    Step 2.
    Open manifest.json,
    2.1 Change the description's value to "_CS_ON_BA_":
        i.e. "description": "_CS_ON_BA_",
        It tells the extension the running environment and to load all setting from ba.json
    2.2 Remove the key attribute from the manifest.json if existing.
        Browser will generate a new key when Captcha Solver extension loaded

    Step 3.
    Open static/ba/ba.json, fill in your credit key, and change the setting as you want.
    Please ensure there are PAID credits under the credit key.

    Step 4.
    Import this script into your Playwright project to work with Captcha Solver extension
    Sample:
        // - import the script
        import { injectCaptchaSolverListener } from 'ba-playwright.js';

        // - tell Captcha Solver extension path
        const extensionPath = "<Captcha Solver extension offline path>";

        // - load Captcha Solver extension
        const context = await chromium.launchPersistentContext('', {
            headless: false,
            args: [
              `--disable-extensions-except=${extensionPath}`,
              `--load-extension=${extensionPath}`
            ]
        });

        // - create a new page
        const page = await context.newPage();

        // - inject the listener into the page with potential CAPTCHA challenges
        await injectCaptchaSolverListener(page);

        // goto the target url with CAPTCHA challenges
        await page.goto('https://accounts.hcaptcha.com/demo');

    Step 5.
    Now Captcha Solver extension will solve challenges on the page automatically when they appear.
*/
export async function injectCaptchaSolverListener(a){await a.exposeFunction("captchaSolverPlaywrightTaskSs",async()=>{await a.waitForTimeout(1e3);return`data:image/png;base64,${(await a.screenshot()).toString("base64")}`}),await a.exposeFunction("captchaSolverPlaywrightTaskExec",async t=>{if("click"===t.action){const e=t.answers,i=t.canvasPosOnView;if(e?.length>0&&i)for(let t=0;t<e.length;t++)await a.mouse.click(e[t].x+i.x,e[t].y+i.y),await a.waitForTimeout(300)}else if("drag"===t.action){const e=t.paths,i=t.canvasPosOnView;if(e?.length>0&&i)for(let t=0;t<e.length;t++){const o=e[t];await a.mouse.move(o.start.x+i.x,o.start.y+i.y),await a.mouse.down(),await a.waitForTimeout(200),await a.mouse.move(o.end.x+i.x,o.end.y+i.y,{steps:15}),await a.mouse.up(),await a.waitForTimeout(300)}}return!0}),await a.addInitScript(()=>{window.addEventListener("cs-request-ba-ss",async()=>{"function"==typeof window.captchaSolverPlaywrightTaskSs&&setTimeout(async()=>{try{const a=await window.captchaSolverPlaywrightTaskSs();window.postMessage({from:"browser-automation",action:"ba-response-cs-ss",dataUrl:a},"*")}catch(a){console.error("Fail to call captchaSolverPlaywrightTaskSs:",a)}},10)}),window.addEventListener("cs-request-ba-op",async a=>{if("function"==typeof window.captchaSolverPlaywrightTaskExec)return await window.captchaSolverPlaywrightTaskExec(a.detail)})})}