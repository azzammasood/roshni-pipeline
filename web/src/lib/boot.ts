// Runs inline in <head> before first paint (no React yet): applies the viewer's saved theme so the
// page never flashes the other theme, and marks the opening animation as already seen after the
// first page of a browser session. Storage may be blocked: the defaults then apply.
export const BOOT_SCRIPT = `try{var d=document.documentElement,t=localStorage.getItem("roshni:theme");if(t==="light"||t==="dark")d.dataset.theme=t;if(sessionStorage.getItem("roshni:intro"))d.classList.add("intro-seen");else sessionStorage.setItem("roshni:intro","1")}catch(e){}`;
