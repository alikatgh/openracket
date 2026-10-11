#!/usr/bin/env python3
"""Strict source-scope gate; semantic tests still require actual Racket.

Usage: python3 check_interval_map_source.py STOCK_MODULE CANDIDATE_MODULE
The candidate must reduce byte-for-byte to the supplied stock source by removing
the one default-off flag/export block and restoring the single setter tail.
"""
import argparse
import hashlib
from pathlib import Path


FLAG_BLOCK = ''';; OpenRacket experiment: avoid a second general traversal after removal has
;; established that the complete interval is empty. Public contracts, removal,
;; interval boundaries and all other operations remain the stock definitions.
(define openracket-interval-map-fast-set-enabled?
  (equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1"))
(provide openracket-interval-map-fast-set-enabled?)

'''
STOCK_TAIL = '''  (interval-map-remove! im start end)
  (interval-map-update*! im start end (lambda (old) value) #f))'''
CANDIDATE_TAIL = '''  (interval-map-remove! im start end)
  (if openracket-interval-map-fast-set-enabled?
      (skip-list-set! (interval-map-s im) start (cons (- end start) value))
      (interval-map-update*! im start end (lambda (old) value) #f)))'''


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(stock: str, candidate: str) -> None:
    require(candidate.count(FLAG_BLOCK) == 1, "one exact default-off flag/export block required")
    require(candidate.count(CANDIDATE_TAIL) == 1, "one bounded setter conditional required")
    require(stock.count(STOCK_TAIL) == 1, "stock setter seam must match expected official source")
    restored = candidate.replace(FLAG_BLOCK, "", 1).replace(CANDIDATE_TAIL, STOCK_TAIL, 1)
    require(restored == stock, "candidate changes more than flag/export plus setter tail")
    require(candidate.count('(getenv "OPENRACKET_INTERVAL_MAP_FAST_SET")') == 1,
            "exactly one environment observation required")
    require(candidate.count('(if openracket-interval-map-fast-set-enabled?') == 1,
            "exactly one optimization branch required")
    require('(equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1")' in candidate,
            "only literal flag value1 may enable the branch")
    # This exact equality covers the complete unchanged provide/contract block,
    # including callback contracts and all interval/key/value/iterator exports.
    marker = "(provide/contract\n"
    require(marker in stock and marker in candidate, "public contracts missing")
    require(candidate[candidate.index(marker):] == stock[stock.index(marker):],
            "public contracts or trailing source changed")
    # Check the test catches accidentally enabled defaults and unrelated edits.
    for corrupted in (
        candidate.replace('(equal? (getenv "OPENRACKET_INTERVAL_MAP_FAST_SET") "1")', '#t', 1),
        candidate.replace('(define (interval-map-cons*!', '(define (unexpected-cons*!', 1),
        candidate.replace('[_r void?]', '[_r any/c]', 1),
    ):
        reverted = corrupted.replace(FLAG_BLOCK, "", 1).replace(CANDIDATE_TAIL, STOCK_TAIL, 1)
        require(reverted != stock, "source-scope self-check failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    stock = args.stock.read_text(encoding="utf-8")
    candidate = args.candidate.read_text(encoding="utf-8")
    validate(stock, candidate)
    print("PASS source scope: default-off flag, one setter branch, untouched contracts and remaining source")
    print("stock_sha256=" + hashlib.sha256(args.stock.read_bytes()).hexdigest())
    print("candidate_sha256=" + hashlib.sha256(args.candidate.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
