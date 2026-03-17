package traceenv.service;

import edu.fudan.common.util.Response;
import org.springframework.http.HttpHeaders;

public interface TraceenvTestService {

    Response test(HttpHeaders headers);

    Response callOrderService(HttpHeaders headers);

    Response callPreserveService(HttpHeaders headers);

    Response callPreserveOtherService(HttpHeaders headers);

    Response callTrainService(HttpHeaders headers);

    Response callTravelService(HttpHeaders headers);

    Response callPaymentService(HttpHeaders headers);

    Response callAll(HttpHeaders headers);
}
