export interface TokenEntry {
  token: string;
  charStart: number;
  charEnd: number;
}

export type TokenMap = TokenEntry[];

export function buildTokenMap(text: string): TokenMap {
  const tokens = text.split(/\s+/);
  const map: TokenMap = [];
  let offset = 0;
  for (const token of tokens) {
    if (token.length === 0) continue;
    const start = text.indexOf(token, offset);
    map.push({ token, charStart: start, charEnd: start + token.length });
    offset = start + token.length;
  }
  return map;
}

export function spanToTokenRange(
  tokenMap: TokenMap,
  charStart: number,
  charEnd: number,
): number[] {
  const indices: number[] = [];
  for (let i = 0; i < tokenMap.length; i++) {
    const { charStart: ts, charEnd: te } = tokenMap[i];
    if (ts >= charStart && te <= charEnd) {
      indices.push(i);
    }
  }
  return indices;
}
