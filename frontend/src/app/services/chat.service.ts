import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
@Injectable()
export class ChatService {

  constructor(private http:HttpClient) { }

  converse(intent, botId = 'default') {
    return this.http.post(environment.ikyBackend + `api/v1`, intent).toPromise();
  }

}
