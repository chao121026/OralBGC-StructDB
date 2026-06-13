document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-value]');
  if (!button) return;
  const value = button.getAttribute('data-copy-value') || '';
  try {
    await navigator.clipboard.writeText(value);
    const previous = button.textContent;
    button.textContent = 'Copied';
    setTimeout(() => { button.textContent = previous; }, 1200);
  } catch (error) {
    button.textContent = 'Copy failed';
  }
});
