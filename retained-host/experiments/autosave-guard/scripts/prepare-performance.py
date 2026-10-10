#!/usr/bin/env python3
"""Generate a separate genuine settled-editor autosave benchmark, no installation."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HOST_SHA = 'b803200cf79fbbacbbdfa16879c9b577ca61d79728a66cf1a0a745d560e58a4f'
RUN_SHA = 'a455819c4c55f25cf2f8cda64df192ea205d768ff659edac71b5b71ca56b67bb'

WORKLOAD = '''  ;; This separate workload starts with a real comment edit already made
  ;; and the stock lexer valid. Background expansion completion is not claimed.
  (set! phase "autosave_preparation")
  (define original-file-bytes (file->bytes fixture))
  (define original-filename (send editor get-filename))
  (define original-format (send editor get-file-format))
  (unless (send editor is-modified?)
    (error 'autosave-preparation "the real comment edit did not mark the document dirty"))
  (unless (send editor autosave?)
    (error 'autosave-preparation "stock autosave is disabled"))
  (record! 'autosave_preconditions
           (hasheq 'lexer_valid (send editor is-lexer-valid?)
                   'modified #t 'autosave_enabled #t
                   'original_filename (~a original-filename)
                   'original_format (~a original-format)
                   'forced_dirty_precondition "set-modified #t after real edit and lexer settle; no intervening GUI yield"))
  (define-values (fixture-directory fixture-name fixture-directory?) (split-path fixture))
  (define existing-artifact-paths (directory-list fixture-directory #:build? #t))
  (define toc-path
    (build-path (find-system-path 'pref-dir)
                (if (eq? (system-type) 'unix) ".plt-autosave-toc.rktd" "PLT-autosave-toc.rktd")))
  (define (read-toc)
    (if (file-exists? toc-path)
        (parameterize ([read-accept-reader #f] [read-accept-lang #f])
          (call-with-input-file toc-path read))
        null))
  (define prior-toc (read-toc))
  (unless (list? prior-toc) (error 'autosave-preparation "unexpected stock recovery TOC shape"))
  (define fixture-prior-entries
    (for/list ([entry (in-list prior-toc)]
               #:when (and (list? entry) (= (length entry) 2)
                            (equal? (car entry) (path->bytes original-filename))))
      entry))
  (record! 'autosave_prior_state
           (hasheq 'toc_present (file-exists? toc-path) 'toc_entry_count (length prior-toc)
                   'fixture_toc_entry_count (length fixture-prior-entries)
                   'fixture_existing_artifact_count
                   (for/sum ([entry (in-list fixture-prior-entries)])
                     (if (and (bytes? (cadr entry)) (file-exists? (bytes->path (cadr entry)))) 1 0))
                   'toc_entries (~s prior-toc)
                   'directory_entries (map path->string existing-artifact-paths)))
  (set! phase "actual_autosave")
  ;; Queue a single GUI probe before the synchronous operation. Unlike the
  ;; periodic heartbeat it cannot miss a save shorter than one sampling period.
  (define probe-delay #f)
  (define probe-submitted (now))
  (queue-callback (lambda () (set! probe-delay (- (now) probe-submitted))) #t)
  ;; The stock timer may already have saved during the initial lexer wait.
  ;; Its documented setter marks any prior autosave out-of-date. No GUI yield
  ;; intervenes before do-autosave; the timed method must execute its real write.
  (send editor set-modified #t)
  (define memory-before-save (memory-snapshot))
  (define save-start (now))
  (define auto-name (send editor do-autosave))
  (define command-returned (now))
  (define memory-after-save-command (memory-snapshot))
  (fence!)
  (define save-finished (now))
  (define memory-after-save-fence (memory-snapshot))
  (define save-timing
    (hasheq 'command_ms (- command-returned save-start)
            'command_plus_low_priority_fence_ms (- save-finished save-start)))
  (unless probe-delay (error 'actual-autosave "queued GUI probe did not dispatch before the fence"))
  (record! 'actual_autosave save-timing)
  (record! 'autosave_queued_gui_probe_ms probe-delay)
  (record! 'actual_autosave_interval
           (hasheq 'started_ms (- save-start started) 'finished_ms (- save-finished started)))
  ;; No JSON persistence occurs between the before and after snapshots.
  (record! 'memory_before_autosave memory-before-save)
  (record! 'memory_after_autosave_command memory-after-save-command)
  (record! 'memory_after_autosave memory-after-save-fence)
  (record! 'autosave_memory_scope
           "command snapshot before fence; final snapshot after fence; both before JSON persistence; runtime-wide counters")
  (set! phase "autosave_recovery_verification")
  (unless (and (path-string? auto-name) (file-exists? auto-name))
    (error 'actual-autosave "no real recovery artifact was produced"))
  (define-values (auto-directory auto-filename auto-directory?)
    (split-path (path->complete-path auto-name)))
  (unless (equal? (simplify-path auto-directory #f) (simplify-path fixture-directory #f))
    (error 'actual-autosave "artifact is outside the directory covered by the preexisting-path witness"))
  (when (member (path->complete-path auto-name) existing-artifact-paths)
    (error 'actual-autosave "returned an already-existing artifact instead of a newly generated save"))
  (unless (equal? (send editor get-filename) original-filename)
    (error 'actual-autosave "original editor filename changed"))
  (unless (eq? (send editor get-file-format) original-format)
    (error 'actual-autosave "original editor format was not restored"))
  (unless (send editor is-modified?)
    (error 'actual-autosave "copy autosave cleared the document's modified state"))
  (unless (bytes=? original-file-bytes (file->bytes fixture))
    (error 'actual-autosave "original document file was modified"))
  (define original-source (bytes->string/utf-8 original-file-bytes))
  (define expected-source
    (string-append (substring original-source 0 edit-pos) "x"
                   (substring original-source edit-pos)))
  (unless (string=? (send editor get-text) expected-source)
    (error 'actual-autosave "full source differs from the single intended comment edit"))
  (define native-text% (dynamic-require 'racket/gui/base 'text%))
  (define restored (new native-text%))
  (unless (send restored load-file auto-name 'guess #f)
    (error 'actual-autosave "recovery artifact did not load in a fresh native editor"))
  (unless (string=? (send restored get-text) expected-source)
    (error 'actual-autosave "recovered source differs from the actual document"))
  (unless (member (list (path->bytes original-filename)
                        (path->bytes (path->complete-path auto-name))) (read-toc))
    (error 'actual-autosave "new artifact is absent from the real recovery TOC"))
  (record! 'autosave_recovery
           (hasheq 'artifact_path (~a auto-name) 'artifact_bytes (file-size auto-name)
                   'recovered_characters (send restored last-position)
                   'exact_recovered_source #t 'original_file_unchanged #t
                   'filename_restored #t 'format_restored #t 'still_modified #t
                   'new_artifact_path_verified #t 'recovery_toc_entry_verified #t))
  (set! phase "final_lexer_settle")
  (define final-settle (await-lexer! editor))
  (record! 'final_lexer_settle final-settle)
  (unless (hash-ref final-settle 'complete)
    (error 'final-lexer-settle "lexer did not become valid after autosave verification"))
'''


def prepare(source, target):
    source, target = Path(source), Path(target)
    host, run = (source / 'retained-host.rkt').read_bytes(), (source / 'run.py').read_bytes()
    if hashlib.sha256(host).hexdigest() != HOST_SHA or hashlib.sha256(run).hexdigest() != RUN_SHA:
        raise ValueError('Frozen benchmark changed; review the transformation before regenerating')
    host = host.decode()
    start, end = host.index('  (set! phase "warm_typing")\n'), host.index('  (set! phase "idle")\n')
    output = host[:start] + WORKLOAD + host[end:]
    output = output.replace('[else "ordinary_timing"]', '[else "settled_editor_autosave"]')
    output = output.replace("      framework:spell-check-on? framework:spell-check-strings? framework:spell-check-text?))",
                            "      framework:spell-check-on? framework:spell-check-strings? framework:spell-check-text?\n"
                            "      framework:autosaving-on? framework:autosave-delay\n"
                            "      framework:backup-files? framework:verify-change-format))")
    output = output.replace('(define-runtime-path activation-path "activation.rkt")',
                            '(define-runtime-path activation-path "activation.rkt")\n'
                            '(define-runtime-path autosave-activation-path "autosave-activation.rkt")')
    output = output.replace('"OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS")])',
                            '"OPENRACKET_EXPERIMENTAL_COLOR_BUDGET_MS"\n'
                            '                            "OPENRACKET_EXPERIMENTAL_SAVE_SCAN_GUARD")])')
    output = output.replace("  (record! 'memory_before_open (memory-snapshot))",
                            "  (record! 'autosave_activation\n"
                            "           ((dynamic-require autosave-activation-path 'verify-autosave-activation)\n"
                            "            (hash-ref config 'autosave_activation \"none\")))\n"
                            "  (record! 'memory_before_open (memory-snapshot))")
    run = run.decode().replace("else 'ordinary_timing'", "else 'settled_editor_autosave'")
    run = run.replace("'scan_activation', 'loaded_characters'",
                      "'scan_activation', 'autosave_activation', 'loaded_characters'")
    run = run.replace("'initial_open_to_lexer_observation_ms', 'warm_input_phase_ms',",
                      "'initial_open_to_lexer_observation_ms', 'actual_autosave', 'autosave_recovery',\n"
                      "        'autosave_queued_gui_probe_ms',\n"
                      "        'autosave_preconditions', 'autosave_prior_state', 'memory_before_autosave', 'memory_after_autosave',\n"
                      "        'memory_after_autosave_command', 'autosave_memory_scope',")
    run = run.replace("'scan_activation': getattr(args, 'scan_activation', 'none')})",
                      "'scan_activation': getattr(args, 'scan_activation', 'none'),\n"
                      "        'autosave_activation': getattr(args, 'autosave_activation', 'none')})")
    run = run.replace("    parser.add_argument('--scan-activation'",
                      "    parser.add_argument('--autosave-activation', choices=['none', 'stock', 'candidate'], default='none')\n"
                      "    parser.add_argument('--scan-activation'")
    target.mkdir(parents=True, exist_ok=True)
    files = {'retained-host.rkt': output.encode(), 'run.py': run.encode()}
    files['autosave-activation.rkt'] = (Path(__file__).resolve().parents[1] / 'performance/autosave-activation.rkt').read_bytes()
    for name in ('fixtures.py', 'settings.rkt', 'diagnostics.rkt', 'activation.rkt', 'test_harness.py'):
        files[name] = (source / name).read_bytes()
    for name, data in files.items():
        (target / name).write_bytes(data)
    manifest = {'measurement_kind': 'settled_editor_autosave', 'source_host_sha256': HOST_SHA,
                'source_run_sha256': RUN_SHA,
                'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (target / 'workload.patch').write_text(''.join(difflib.unified_diff(
        host.splitlines(True), output.splitlines(True), fromfile='baseline/retained-host.rkt',
        tofile='autosave/retained-host.rkt')))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'performance')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))
