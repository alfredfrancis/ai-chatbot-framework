import { Injectable } from '@angular/core';
import { Http, RequestOptions, Headers } from '@angular/http';

@Injectable()
export class CoreService {
  static apiUrl = 'http://localhost:8001';
  constructor(public http: Http) { }

  doHeaders(data: any = null) {
    const headerVals: any = { 'Content-Type': 'application/json' };
    return new Headers(headerVals);
  }

  doRead(method: string, url: string, query = null, resJson = true) {
    return new Promise((resolve, reject) => {
      const headers = this.doHeaders(null);
      const options = new RequestOptions({ headers: headers, method: method });
      const finalUrl = this.doQueryString(CoreService.apiUrl + url, query);
      // console.log(`GET: ${finalUrl}`);
      const promise = this.http.get(finalUrl, options);
      // if (resJson) {
      //   promise = promise.then(res => res.json());
      // }
      return promise.subscribe((data: any) => {
        if (data && data._body) {
          resolve(JSON.parse(data._body));
        } else {
          resolve(data);
        }
      },
        error => {
          reject(error);
        });
    });
  }

  doGet(url: string, query = null, resJson = true) {
    return this.doRead('get', url, query, resJson);
  }

  doDelete(url: string, query = null, resJson = true) {
    return this.doRead('delete', url, query, resJson);
  }


  doPost(url: string, data: any, files: any = null) {
    return this.doSubmit('post', url, data, files);
  }

  doPut(url: string, data: any, files: any = null) {
    return this.doSubmit('put', url, data, files);
  }

  doSubmit(method: string, url: string, data: any, files: any = null) {
    return new Promise((resolve, reject) => {
      const headers = this.doHeaders(data);
      const options = new RequestOptions({
        headers: headers,
        method: method
      });
      if (!data) {
        data = {};
      }

      let formData;

      if (files) {
        formData = new FormData();
        if (files.length === 1) {
          formData.append('uploads', files[0], files[0].name);
        } else {
          for (let i = 0; i < files.length; i++) {
            formData.append('uploads[]', files[i], files[i].name);
          }
        }
      } else {
        formData = JSON.stringify(data);
      }
      console.log(`POST: ${CoreService.apiUrl + url}`);
      return this.http.post(CoreService.apiUrl + url, formData, options)
        // .map(res => res.json())
        .subscribe((dataAnswer: any) => {
          if (dataAnswer && dataAnswer._body) {
            resolve(JSON.parse(dataAnswer._body));
          } else {
            resolve(dataAnswer);
          }
        },
        error => {
          reject(error);
        });
    });
  }

  doQueryString(url, queries) {
    if (queries) {
      url += '?';
      for (const key in queries) {
        url += `&${key}=${queries[key]}`;
      }
    }
    return url;
  }

}
