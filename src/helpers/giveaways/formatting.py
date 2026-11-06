from __future__ import annotations

import re
from urllib.parse import urlparse


def parse_duration(value: str) -> int:
    text = (value or '').strip().lower().replace(',', '.')
    pattern = re.compile('(\\d+)\\s*(d|dia|dias|h|hora|horas|m|min|minuto|minutos)')
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError('Informe uma duração como `30m`, `2h` ou `1d 4h`.')
    remainder = pattern.sub('', text).strip()
    if remainder:
        raise ValueError('Duração inválida. Use exemplos como `30m`, `2h` ou `1d 4h`.')
    total = 0
    for match in matches:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in {'d', 'dia', 'dias'}:
            total += amount * 86400
        elif unit in {'h', 'hora', 'horas'}:
            total += amount * 3600
        else:
            total += amount * 60
    if total < 60:
        raise ValueError('O sorteio precisa durar pelo menos 1 minuto.')
    if total > 365 * 86400:
        raise ValueError('A duração máxima de um sorteio é 365 dias.')
    return total

def _valid_url(value: str) -> bool:
    if not value:
        return True
    try:
        parsed = urlparse(value)
        return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
    except ValueError:
        return False

def format_duration(seconds: int) -> str:
    seconds = int(seconds or 0)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    parts = []
    if days:
        parts.append(f'{days}d')
    if hours:
        parts.append(f'{hours}h')
    if minutes or not parts:
        parts.append(f'{minutes}m')
    return ' '.join(parts)
