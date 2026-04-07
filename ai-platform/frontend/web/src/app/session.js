export function clearFixmeSessionStorage() {
  const toRemove = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key && key.startsWith('fixme_')) {
      toRemove.push(key);
    }
  }
  toRemove.forEach((key) => localStorage.removeItem(key));
}
