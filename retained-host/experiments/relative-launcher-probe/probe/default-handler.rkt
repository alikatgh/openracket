#lang racket/base
;; Optional CI witness only. This CLI performs native read-only queries and
;; writes JSON to stdout. It never registers an app, opens a file, or sets defaults.
(require ffi/unsafe ffi/unsafe/objc ffi/unsafe/nsalloc json)
(provide read-rkt-default-handler)
(define (read-rkt-default-handler)
  (unless (eq? (system-type 'os) 'macosx) (error 'default-handler "Requires native macOS"))
  (define foundation (ffi-lib "/System/Library/Frameworks/Foundation.framework/Foundation"))
  (define core (ffi-lib "/System/Library/Frameworks/CoreServices.framework/CoreServices"))
  (define cf (ffi-lib "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"))
  (define release (get-ffi-obj "CFRelease" cf (_fun _pointer -> _void)))
  (define preferred (get-ffi-obj "UTTypeCreatePreferredIdentifierForTag" core (_fun _id _id _id -> _id)))
  (define default-handler (get-ffi-obj "LSCopyDefaultRoleHandlerForContentType" core (_fun _id _uint32 -> _id)))
  ;; Borrowed exported constant: never released.
  (define extension-tag (get-ffi-obj "kUTTagClassFilenameExtension" core _id))
  (import-class NSString)
  (define (as-string value) (tell #:type _string/utf-8 value UTF8String))
  (with-autorelease
    (define extension (tell NSString stringWithUTF8String: #:type _string/utf-8 "rkt"))
    (define uti (preferred extension-tag extension #f))
    (unless uti (error 'default-handler "UTI query returned NULL for the known filename-extension tag class"))
    (dynamic-wind
      void
      (lambda ()
        (define handler (default-handler uti #xffffffff))
        (dynamic-wind
          void
          (lambda ()
            (hash 'schema 1 'status "observed" 'extension "rkt"
                  'uti (as-string uti) 'role_mask 4294967295
                  'default_handler (if handler (as-string handler) 'null)
                  'handler_available (and handler #t)
                  'query "UTTypeCreatePreferredIdentifierForTag + LSCopyDefaultRoleHandlerForContentType"
                  'defaults_changed #f))
          (lambda () (when handler (release handler)))))
      (lambda () (release uti)))))
(module+ main
  (with-handlers ([exn:fail?
                   (lambda (e)
                     (write-json (hash 'schema 1 'status "error" 'error (exn-message e)))
                     (newline) (exit 1))])
    (write-json (read-rkt-default-handler)) (newline)))
