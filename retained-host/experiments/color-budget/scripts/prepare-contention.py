#!/usr/bin/env python3
"""Build a separate early-typing workload; never modify the frozen scan harness."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path


HOST_SHA = 'b803200cf79fbbacbbdfa16879c9b577ca61d79728a66cf1a0a745d560e58a4f'
RUN_SHA = 'a455819c4c55f25cf2f8cda64df192ea205d768ff659edac71b5b71ca56b67bb'

WORKLOAD = '''  ;; Separate experiment: type while initial coloring may still be pending.
  ;; This is deliberately not comparable to the settled-input scan workload.
  (record! 'memory_before_contention (memory-snapshot))
  (set! phase "initial_coloring_typing")
  (define contention-start (now))
  (define next-contention-deadline (+ contention-start 16.0))
  (define contention-reversed null)
  (define contention-error #f)
  ;; One outstanding request avoids an unbounded synthetic input backlog.
  ;; The producer sleeps off the GUI thread and timestamps actual enqueueing.
  (define contention-producer
    (thread
     (lambda ()
       (for ([i (in-range 80)] #:break contention-error)
         (define scheduled next-contention-deadline)
         (sleep (max 0 (/ (- scheduled (now)) 1000.0)))
         (define done (make-semaphore))
         (define submitted (now))
         (queue-callback
          (lambda ()
            (with-handlers ([(lambda (_) #t) (lambda (e) (set! contention-error (cons 'raised e)))])
              (define dispatched (now))
              (define valid-before? (send editor is-lexer-valid?))
              (define editor-completed #f)
              (define sample
                (timed-command (lambda ()
                                 (send editor on-char (new key-event% [key-code #\\a]))
                                 (set! editor-completed (now)))))
              (define fenced (now))
              (define valid-after? (send editor is-lexer-valid?))
              (define dispatch-ms (- dispatched submitted))
              (set! contention-reversed
                    (cons (for/fold ([result sample])
                                    ([key '(ordinal lexer_valid_before lexer_valid_after
                                                    queue_to_handler_ms
                                                    queue_to_editor_completion_ms
                                                    queue_to_fence_ms
                                                    producer_scheduling_delay_ms
                                                    scheduled_to_editor_completion_ms
                                                    scheduled_to_fence_ms)]
                                     [value (list i valid-before? valid-after? dispatch-ms
                                                  (- editor-completed submitted)
                                                  (- fenced submitted)
                                                  (max 0 (- submitted scheduled))
                                                  (- editor-completed scheduled)
                                                  (- fenced scheduled))])
                            (hash-set result key value))
                          contention-reversed))
              (set! next-contention-deadline (+ fenced 16.0)))
            (semaphore-post done)) #t)
         (semaphore-wait done)))))
  (gui-yield (thread-dead-evt contention-producer))
  (when contention-error
    (if (exn? (cdr contention-error))
        (raise (cdr contention-error))
        (error 'initial-coloring-typing "callback raised a non-exception: ~e" (cdr contention-error))))
  (define contention-samples (reverse contention-reversed))
  (unless (= (length contention-samples) 80)
    (error 'initial-coloring-typing "producer did not complete exactly 80 requests"))
  (define contention-elapsed (- (now) contention-start))
  (record! 'initial_coloring_key_samples contention-samples)
  (record! 'initial_coloring_typing_phase_ms contention-elapsed)
  (record! 'keys_starting_with_lexer_invalid
           (for/sum ([sample (in-list contention-samples)])
             (if (hash-ref sample 'lexer_valid_before) 0 1)))
  (record! 'memory_after_contention (memory-snapshot))
  (unless (= (send editor last-position) (+ expected-size 81))
    (error 'initial-coloring-typing "synthetic editor key count mismatch"))
  (unless (string=? (send editor get-text edit-pos (+ edit-pos 81))
                   (string-append "x" (make-string 80 #\\a)))
    (error 'initial-coloring-typing "synthetic input content mismatch"))
  (set! phase "post_typing_lexer_settle")
  (define post-typing-settle (await-lexer! editor))
  (define completed-workload-ms (- (now) initial-open-start))
  (record! 'post_typing_lexer_settle post-typing-settle)
  (record! 'open_to_completed_workload_ms completed-workload-ms)
  (unless (hash-ref post-typing-settle 'complete)
    (error 'post-typing-lexer-settle "lexer did not become valid within 45 seconds"))
  (record! 'memory_after_post_typing_settle (memory-snapshot))
'''


def prepare(source, target):
    source, target = Path(source), Path(target)
    host = (source / 'retained-host.rkt').read_bytes()
    run = (source / 'run.py').read_bytes()
    if hashlib.sha256(host).hexdigest() != HOST_SHA or hashlib.sha256(run).hexdigest() != RUN_SHA:
        raise ValueError('Frozen scan harness changed; review before generating a new workload')
    host = host.decode()
    start = host.index('  (set! phase "initial_lexer_settle")\n')
    end = host.index('  (set! phase "idle")\n', start)
    output = host[:start] + WORKLOAD + host[end:]
    output = output.replace('[else "ordinary_timing"]', '[else "initial_coloring_typing"]')
    output = output.replace('(define-runtime-path activation-path "activation.rkt")',
                            '(define-runtime-path activation-path "activation.rkt")\n'
                            '(define-runtime-path budget-activation-path "budget-activation.rkt")')
    output = output.replace("  (record! 'memory_before_open (memory-snapshot))",
                            "  (record! 'budget_activation\n"
                            "           ((dynamic-require budget-activation-path 'verify-budget-activation)\n"
                            "            (hash-ref config 'budget_activation \"none\")))\n"
                            "  (record! 'memory_before_open (memory-snapshot))")
    output = output.replace('  ;; Explicit collection only after all latency work;', '''  ;; Full source comparison is deliberately outside every timed/GC workload.
  (define original-source (file->string fixture))
  (define expected-source
    (string-append (substring original-source 0 edit-pos) "x" (make-string 80 #\\a)
                   (substring original-source edit-pos)))
  (unless (string=? (send editor get-text) expected-source)
    (error 'contention-source "Full resulting source differs from the intended edits"))
  (record! 'exact_resulting_source_verified #t)
  ;; Explicit collection only after all latency work;''')
    run = run.decode().replace("else 'ordinary_timing'", "else 'initial_coloring_typing'")
    run = run.replace("'scan_activation', 'loaded_characters'", "'scan_activation', 'budget_activation', 'loaded_characters'")
    run = run.replace("'scan_activation': getattr(args, 'scan_activation', 'none')})",
                      "'scan_activation': getattr(args, 'scan_activation', 'none'),\n"
                      "        'budget_activation': getattr(args, 'budget_activation', 'none')})")
    run = run.replace("    parser.add_argument('--scan-activation'",
                      "    parser.add_argument('--budget-activation', choices=['none', 'stock', '4', '8', '12', '20'], default='none')\n"
                      "    parser.add_argument('--scan-activation'")
    run = run.replace("'initial_open_to_lexer_observation_ms', 'warm_input_phase_ms',",
                      "'initial_coloring_typing_phase_ms', 'keys_starting_with_lexer_invalid',\n"
                      "        'post_typing_lexer_settle', 'open_to_completed_workload_ms',\n"
                      "        'memory_before_contention', 'memory_after_contention',\n"
                      "        'memory_after_post_typing_settle',")
    run = run.replace("('warm_editor_key_samples', 'warm_jump_samples')", "('initial_coloring_key_samples',)")
    run = run.replace("('command_ms', 'command_plus_low_priority_fence_ms')", 
                      "('command_ms', 'command_plus_low_priority_fence_ms',\n"
                      "                                   'queue_to_handler_ms', 'queue_to_editor_completion_ms', 'queue_to_fence_ms',\n"
                      "                                   'producer_scheduling_delay_ms', 'scheduled_to_editor_completion_ms', 'scheduled_to_fence_ms')")
    target.mkdir(parents=True, exist_ok=True)
    files = {'retained-host.rkt': output.encode(), 'run.py': run.encode()}
    files['budget-activation.rkt'] = (Path(__file__).resolve().parents[1] / 'contention/budget-activation.rkt').read_bytes()
    for name in ('fixtures.py', 'settings.rkt', 'diagnostics.rkt', 'activation.rkt', 'test_harness.py'):
        files[name] = (source / name).read_bytes()
    for name, content in files.items():
        (target / name).write_bytes(content)
    manifest = {
        'scope': 'Separate initial-coloring typing measurement only; no runtime optimization installed',
        'source_host_sha256': HOST_SHA, 'source_run_sha256': RUN_SHA,
        'output_sha256': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (target / 'workload.patch').write_text(''.join(difflib.unified_diff(
        host.splitlines(True), output.splitlines(True),
        fromfile='scan/performance/retained-host.rkt', tofile='contention/retained-host.rkt')))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'contention')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))
