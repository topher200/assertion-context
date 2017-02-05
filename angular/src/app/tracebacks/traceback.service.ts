import { Injectable } from '@angular/core';
import { Http } from '@angular/http';
import { Traceback } from './traceback';
import 'rxjs/add/operator/map';

@Injectable()
export class TracebackService {

  constructor(private http: Http) { }

  getTracebacks() {
    return this.http.get('http://127.0.0.1:8080/api/tracebacks')
      .map(response => <Traceback[]>response.json().tracebacks);
  }
}
