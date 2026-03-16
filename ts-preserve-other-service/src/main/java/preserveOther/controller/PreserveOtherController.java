package preserveOther.controller;

import edu.fudan.common.util.Response;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.web.bind.annotation.*;
import edu.fudan.common.entity.OrderTicketsInfo;
import preserveOther.service.PreserveOtherService;

import static org.springframework.http.ResponseEntity.ok;

/**
 * @author fdse
 */
@RestController
@RequestMapping("/api/v1/preserveotherservice")
public class PreserveOtherController {

    @Autowired
    private PreserveOtherService preserveService;

    private static final Logger LOGGER = LoggerFactory.getLogger(PreserveOtherController.class);

    @GetMapping(path = "/welcome")
    public String home() {
        return "Welcome to [ PreserveOther Service ] !";
    }

    @GetMapping(path = "/traceenv")
    public HttpEntity traceenv(@RequestHeader HttpHeaders headers) {
        return ok(new Response<>(1, "yes, yyl is big D", null));
    }

    @CrossOrigin(origins = "*")
    @PostMapping(value = "/preserveOther")
    public HttpEntity preserve(@RequestBody OrderTicketsInfo oti,
                               @RequestHeader HttpHeaders headers) {
        PreserveOtherController.LOGGER.info("[preserve][Preserve Account order][from {} to {} at {}]", oti.getFrom(), oti.getTo(), oti.getDate());
        return ok(preserveService.preserve(oti, headers));
    }

}
