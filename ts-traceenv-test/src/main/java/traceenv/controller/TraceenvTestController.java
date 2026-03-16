package traceenv.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.web.bind.annotation.*;
import traceenv.service.TraceenvTestService;

import static org.springframework.http.ResponseEntity.ok;

@RestController
@RequestMapping("/api/v1/traceenvtest")
public class TraceenvTestController {

    @Autowired
    private TraceenvTestService traceenvTestService;

    private static final Logger LOGGER = LoggerFactory.getLogger(TraceenvTestController.class);

    @GetMapping(path = "/welcome")
    public String home() {
        return "Welcome to [ TraceenvTest Service ] !";
    }

    @GetMapping(path = "/test")
    public HttpEntity test(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[test][TraceenvTest test endpoint called]");
        return ok(traceenvTestService.test(headers));
    }

    @GetMapping(path = "/call-order")
    public HttpEntity callOrder(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callOrder][Call order service]");
        return ok(traceenvTestService.callOrderService(headers));
    }

    @GetMapping(path = "/call-preserve")
    public HttpEntity callPreserve(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callPreserve][Call preserve service]");
        return ok(traceenvTestService.callPreserveService(headers));
    }

    @GetMapping(path = "/call-preserve-other")
    public HttpEntity callPreserveOther(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callPreserveOther][Call preserve other service]");
        return ok(traceenvTestService.callPreserveOtherService(headers));
    }

    @GetMapping(path = "/call-train")
    public HttpEntity callTrain(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callTrain][Call train service]");
        return ok(traceenvTestService.callTrainService(headers));
    }

    @GetMapping(path = "/call-travel")
    public HttpEntity callTravel(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callTravel][Call travel service]");
        return ok(traceenvTestService.callTravelService(headers));
    }

    @GetMapping(path = "/call-payment")
    public HttpEntity callPayment(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callPayment][Call payment service]");
        return ok(traceenvTestService.callPaymentService(headers));
    }

    @GetMapping(path = "/call-all")
    public HttpEntity callAll(@RequestHeader HttpHeaders headers) {
        TraceenvTestController.LOGGER.info("[callAll][Call all services]");
        return ok(traceenvTestService.callAll(headers));
    }
}
