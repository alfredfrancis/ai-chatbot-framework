import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable()
export class AgentsService {

  constructor(public http: HttpClient) { }

  get_config() {
    return this.http.get(environment.ikyBackend + `agents/default/config`).toPromise();
  }
  update_config(data) {
    return this.http.put(environment.ikyBackend + `agents/default/config`, data).toPromise();
  }

}
