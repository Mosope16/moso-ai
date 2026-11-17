import { spawn } from 'child_process';

class CDPClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (err) => reject(err);
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) {
            reject(new Error(msg.error.message || JSON.stringify(msg.error)));
          } else {
            resolve(msg.result);
          }
        }
      };
    });
  }

  async send(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval exception: ${res.exceptionDetails.text} (${JSON.stringify(res.exceptionDetails.exception)})`);
    }
    return res.result?.value;
  }

  async setViewport(width, height, isMobile = false) {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 2,
      mobile: isMobile
    });
    await this.send('Emulation.setVisibleSize', { width, height });
    // Trigger window resize event in page so React context and CSS breakpoints re-render
    await this.evaluate(`(() => {
      window.dispatchEvent(new Event('resize'));
    })()`);
    await new Promise(r => setTimeout(r, 250));
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

async function runTestSuite() {
  console.log('='.repeat(70));
  console.log('MOSO AI: RESPONSIVE VIEWPORT & MOBILE-FIRST VERIFICATION SUITE');
  console.log('='.repeat(70));

  const brave = spawn('brave', [
    '--headless=new',
    '--remote-debugging-port=9222',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    'http://127.0.0.1:5173'
  ]);

  await new Promise(r => setTimeout(r, 2000));

  let cdp = null;
  let passedCount = 0;
  let totalCount = 0;

  function assert(condition, testName, details = '') {
    totalCount++;
    if (condition) {
      console.log(`  ✓ PASS: ${testName} ${details ? '(' + details + ')' : ''}`);
      passedCount++;
    } else {
      console.error(`  ✗ FAIL: ${testName} ${details ? '(' + details + ')' : ''}`);
      throw new Error(`Assertion failed: ${testName}`);
    }
  }

  try {
    const res = await fetch('http://127.0.0.1:9222/json');
    const tabs = await res.json();
    const pageTab = tabs.find(t => t.type === 'page');
    if (!pageTab) throw new Error('No target page found in Brave');

    cdp = new CDPClient(pageTab.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('DOM.enable');

    // Wait for App to mount
    await new Promise(r => setTimeout(r, 1500));

    const viewports = [
      { name: 'iPhone SE (compact mobile)', width: 320, height: 568, isMobile: true },
      { name: 'iPhone 8 / SE2', width: 375, height: 667, isMobile: true },
      { name: 'iPhone 13 / 14 / 15', width: 390, height: 844, isMobile: true },
      { name: 'iPhone 15 / 16 Pro Max', width: 430, height: 932, isMobile: true },
      { name: 'iPad Portrait (Tablet)', width: 768, height: 1024, isMobile: false },
      { name: 'Standard Laptop (Desktop)', width: 1366, height: 768, isMobile: false },
      { name: 'FHD Monitor (Wide Desktop)', width: 1920, height: 1080, isMobile: false },
    ];

    console.log('\n[STAGE 1] Testing Viewports for Zero Horizontal Overflow');
    for (const vp of viewports) {
      await cdp.setViewport(vp.width, vp.height, vp.isMobile);

      const metrics = await cdp.evaluate(`(() => {
        const docEl = document.documentElement;
        const body = document.body;
        const root = document.getElementById('root');
        return {
          windowInnerWidth: window.innerWidth,
          docScrollWidth: docEl.scrollWidth,
          bodyScrollWidth: body.scrollWidth,
          rootScrollWidth: root ? root.scrollWidth : 0,
          hasHorizontalScroll: (docEl.scrollWidth > window.innerWidth) || (body.scrollWidth > window.innerWidth)
        };
      })()`);

      assert(
        !metrics.hasHorizontalScroll,
        `No horizontal overflow on ${vp.name} (${vp.width}x${vp.height})`,
        `docScrollWidth=${metrics.docScrollWidth}, innerWidth=${metrics.windowInnerWidth}`
      );
    }

    console.log('\n[STAGE 2] Testing Mobile Navigation Drawer (< 768px: 375x667)');
    await cdp.setViewport(375, 667, true);

    // 1. Initial State: Sidebar hidden by default on mobile
    const initialSidebarState = await cdp.evaluate(`(() => {
      const aside = document.querySelector('aside');
      const hamburger = document.querySelector('button[aria-label*="drawer" i], button:has(svg.lucide-menu)');
      const backdrop = document.querySelector('.bg-black\\\\/65, .backdrop-blur-xs');
      return {
        hasAside: !!aside,
        hasHamburger: !!hamburger,
        hasBackdrop: !!backdrop
      };
    })()`);

    assert(
      !initialSidebarState.hasAside && initialSidebarState.hasHamburger && !initialSidebarState.hasBackdrop,
      'Mobile view starts with drawer closed and hamburger visible',
      `aside=${initialSidebarState.hasAside}, hamburger=${initialSidebarState.hasHamburger}`
    );

    // 2. Open drawer by clicking hamburger
    await cdp.evaluate(`(() => {
      const btn = document.querySelector('button[aria-label*="drawer" i], button:has(svg.lucide-menu)');
      if (btn) btn.click();
    })()`);
    await new Promise(r => setTimeout(r, 350));

    const openedDrawerState = await cdp.evaluate(`(() => {
      const aside = document.querySelector('aside');
      const backdrop = document.querySelector('.bg-black\\\\/65, .backdrop-blur-xs');
      const isFixedOverlay = aside ? window.getComputedStyle(aside).position === 'fixed' : false;
      const zIndex = aside ? window.getComputedStyle(aside).zIndex : '0';
      const hasCloseBtn = aside ? !!aside.querySelector('button[aria-label*="sidebar" i], button:has(svg.lucide-x)') : false;
      return {
        hasAside: !!aside,
        hasBackdrop: !!backdrop,
        isFixedOverlay,
        zIndex,
        hasCloseBtn
      };
    })()`);

    assert(
      openedDrawerState.hasAside && openedDrawerState.isFixedOverlay && openedDrawerState.hasBackdrop,
      'Drawer slides in as fixed overlay with backdrop on mobile',
      `position=${openedDrawerState.isFixedOverlay ? 'fixed' : 'not-fixed'}, zIndex=${openedDrawerState.zIndex}`
    );

    // 3. Close drawer via backdrop tap
    await cdp.evaluate(`(() => {
      const backdrop = document.querySelector('.bg-black\\\\/65, .backdrop-blur-xs');
      if (backdrop) backdrop.click();
    })()`);
    await new Promise(r => setTimeout(r, 350));

    const closedByBackdrop = await cdp.evaluate(`(() => {
      return !document.querySelector('aside');
    })()`);
    assert(closedByBackdrop, 'Backdrop tap successfully closes mobile drawer');

    // 4. Open drawer and test Escape key close
    await cdp.evaluate(`(() => {
      const btn = document.querySelector('button[aria-label*="drawer" i], button:has(svg.lucide-menu)');
      if (btn) btn.click();
    })()`);
    await new Promise(r => setTimeout(r, 350));

    await cdp.evaluate(`(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
    })()`);
    await new Promise(r => setTimeout(r, 350));

    const closedByEscape = await cdp.evaluate(`(() => {
      return !document.querySelector('aside');
    })()`);
    assert(closedByEscape, 'Escape key closes mobile drawer');

    // 5. Open drawer and test auto-close on conversation/new-chat selection
    await cdp.evaluate(`(() => {
      const btn = document.querySelector('button[aria-label*="drawer" i], button:has(svg.lucide-menu)');
      if (btn) btn.click();
    })()`);
    await new Promise(r => setTimeout(r, 350));

    await cdp.evaluate(`(() => {
      const newChatBtn = document.querySelector('aside button:has(svg.lucide-plus), aside button');
      if (newChatBtn) newChatBtn.click();
    })()`);
    await new Promise(r => setTimeout(r, 350));

    const closedByAction = await cdp.evaluate(`(() => {
      return !document.querySelector('aside');
    })()`);
    assert(closedByAction, 'Action/Navigation inside drawer auto-closes drawer on mobile');

    console.log('\n[STAGE 3] Testing Mobile Header Overflow & Settings Modal');
    // Test mobile overflow menu
    const overflowOpen = await cdp.evaluate(`(() => {
      const overflowBtn = document.querySelector('button[aria-label="More actions"], button:has(svg.lucide-ellipsis-vertical), button:has(svg.lucide-more-vertical)');
      if (!overflowBtn) return false;
      overflowBtn.click();
      return true;
    })()`);
    assert(overflowOpen, 'Mobile overflow menu button (MoreVertical) is present and clickable');
    await new Promise(r => setTimeout(r, 250));

    // Click Settings from overflow menu
    await cdp.evaluate(`(() => {
      const settingsOption = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Settings'));
      if (settingsOption) settingsOption.click();
    })()`);
    await new Promise(r => setTimeout(r, 450));

    // Verify Settings Modal on mobile
    const settingsModalInfo = await cdp.evaluate(`(() => {
      const dialog = document.querySelector('[role="dialog"], .fixed.inset-0.z-50');
      const title = dialog ? dialog.querySelector('h2, h3') : null;
      const rect = dialog ? dialog.getBoundingClientRect() : null;
      return {
        isOpen: !!dialog,
        titleText: title ? title.textContent : '',
        fitsViewport: rect ? (rect.width <= window.innerWidth && rect.height <= window.innerHeight) : false
      };
    })()`);

    assert(
      settingsModalInfo.isOpen && settingsModalInfo.fitsViewport,
      'Settings Modal opens on mobile and fits within viewport',
      `title=${settingsModalInfo.titleText}, fits=${settingsModalInfo.fitsViewport}`
    );

    // Close Settings Modal
    await cdp.evaluate(`(() => {
      const closeBtn = document.querySelector('button[aria-label="Close dialog"]');
      if (closeBtn) {
        closeBtn.click();
      } else {
        const backdrop = document.querySelector('.bg-black\\\\/75');
        if (backdrop) backdrop.click();
      }
    })()`);
    await new Promise(r => setTimeout(r, 400));

    console.log('\n[STAGE 4] Testing Chat Composer & Input Layout on Mobile');
    const composerMetrics = await cdp.evaluate(`(() => {
      const textarea = document.querySelector('textarea');
      const container = textarea ? textarea.closest('.rounded-full, .rounded-2xl, .rounded-3xl') : null;
      const sendBtn = container ? container.querySelector('button[aria-label="Send message"], button:has(svg.lucide-arrow-up)') : null;
      const paperclipBtn = container ? container.querySelector('button[aria-label="Attach PDF document"], button:has(svg.lucide-paperclip), button:has(svg.lucide-plus)') : null;
      const hasDisclaimer = Array.from(document.querySelectorAll('p, div')).some(el => el.textContent && el.textContent.includes('can make mistakes'));
      
      const containerRect = container ? container.getBoundingClientRect() : null;
      const textareaRect = textarea ? textarea.getBoundingClientRect() : null;
      const sendRect = sendBtn ? sendBtn.getBoundingClientRect() : null;

      // Ensure send button does not overlap textarea vertically or horizontally
      const noOverlap = sendRect && textareaRect ? (textareaRect.bottom <= sendRect.bottom) : true;

      return {
        hasTextarea: !!textarea,
        hasSendBtn: !!sendBtn,
        hasPaperclip: !!paperclipBtn,
        hasDisclaimer,
        containerWidth: containerRect ? Math.round(containerRect.width) : 0,
        windowWidth: window.innerWidth,
        noOverlap
      };
    })()`);

    assert(
      composerMetrics.hasTextarea && composerMetrics.hasSendBtn && composerMetrics.hasPaperclip && composerMetrics.hasDisclaimer,
      'Chat Composer layout is minimized and includes AI mistakes disclaimer',
      `containerWidth=${composerMetrics.containerWidth}px in ${composerMetrics.windowWidth}px viewport, disclaimer=${composerMetrics.hasDisclaimer}`
    );

    console.log('\n[STAGE 5] Testing Desktop Layout (>= 768px: 1366x768)');
    await cdp.setViewport(1366, 768, false);
    await new Promise(r => setTimeout(r, 400));

    const desktopState = await cdp.evaluate(`(() => {
      const aside = document.querySelector('aside');
      const asideStyle = aside ? window.getComputedStyle(aside) : null;
      const isRelativeOrStatic = asideStyle ? (asideStyle.position === 'relative' || asideStyle.position === 'static') : false;
      const hamburgerMobile = document.querySelector('.flex.md\\\\:hidden button[aria-label*="drawer" i]');
      const isHamburgerHidden = !hamburgerMobile || window.getComputedStyle(hamburgerMobile).display === 'none';
      const mainChat = document.querySelector('main');
      return {
        hasAside: !!aside,
        isRelativeOrStatic,
        isHamburgerHidden,
        hasMainChat: !!mainChat
      };
    })()`);

    assert(
      desktopState.hasAside && desktopState.isRelativeOrStatic,
      'Desktop sidebar is in normal document flow (relative, not overlay drawer)',
      `position=${desktopState.isRelativeOrStatic ? 'relative' : 'overlay'}`
    );

    console.log('\n' + '='.repeat(70));
    console.log(`ALL TESTS PASSED: ${passedCount} / ${totalCount} checks succeeded!`);
    console.log('='.repeat(70));
  } catch (err) {
    console.error('\nSuite Execution Error:', err);
    process.exitCode = 1;
  } finally {
    if (cdp) cdp.close();
    brave.kill();
  }
}

runTestSuite();
