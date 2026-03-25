/*
    Steps to integrate Captcha Solver into your Puppeteer project.
    Step 1.
    Download the Captcha Solver extension and save it to your project folder.

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
    Import this script into your Puppeteer project to use Captcha Solver extension
    Sample:
        // - import the script
        import { injectCaptchaSolverListener } from 'ba-puppeteer.js';

        // - tell the offline extension path
        const extensionPath = "<Captcha Solver extension offline path>";

        // - load Captcha Solver extension
        const browser = await puppeteer.launch({
          headless: false,
          args: [
          `--disable-extensions-except=${extensionPath}`,
          `--load-extension=${extensionPath}`
          ]
        });

        // - create a new page
        const page = await browser.newPage();

        // - inject the listener into the page with potential CAPTCHA challenges
        await injectCaptchaSolverListener(page);

        // goto the target url with CAPTCHA challenges
        await page.goto('https://accounts.hcaptcha.com/demo');

    Step 5.
    Now Captcha Solver extension will solve challenges on the page automatically when they appear.
*/
export async function injectCaptchaSolverListener(e){await e.exposeFunction("captchaSolverPuppeteerTaskSs",async()=>{await e.waitForTimeout(1e3);return`data:image/png;base64,${(await e.screenshot()).toString("base64")}`}),await e.exposeFunction("captchaSolverPuppeteerTaskExec",async a=>{if("click"===a.action){const t=a.answers,o=a.canvasPosOnView;if(t?.length>0&&o)for(let a=0;a<t.length;a++)await e.mouse.click(t[a].x+o.x,t[a].y+o.y),await e.waitForTimeout(300)}else if("drag"===a.action){const t=a.paths,o=a.canvasPosOnView;if(t?.length>0&&o)for(let a=0;a<t.length;a++){const s=t[a];await e.mouse.move(s.start.x+o.x,s.start.y+o.y),await e.mouse.down(),await e.waitForTimeout(200),await e.mouse.move(s.end.x+o.x,s.end.y+o.y,{steps:15}),await e.mouse.up(),await e.waitForTimeout(300)}}return!0}),await e.evaluateOnNewDocument(()=>{window.addEventListener("cs-request-ba-ss",async()=>{"function"==typeof window.captchaSolverPuppeteerTaskSs&&setTimeout(async()=>{try{const e=await window.captchaSolverPuppeteerTaskSs();window.postMessage({from:"browser-automation",action:"ba-response-cs-ss",dataUrl:e},"*")}catch(e){console.error("Error calling captchaSolverPuppeteerTaskSs:",e)}},10)}),window.addEventListener("cs-request-ba-op",async e=>{if("function"==typeof window.captchaSolverPuppeteerTaskExec)return await window.captchaSolverPuppeteerTaskExec(e.detail)})})}