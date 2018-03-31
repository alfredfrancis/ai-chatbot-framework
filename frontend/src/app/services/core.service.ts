import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { FormGroup } from '@angular/forms';

@Injectable()
export class CoreService {
  static apiUrl = 'http://localhost:8001';
  constructor(public http: HttpClient) { }

  doHeaders(data: any = null) {
    const headerVals: any = { 'Content-Type': 'application/json' };
    if (localStorage.botToken) {
      headerVals.Authorization = `Basic ${localStorage.botToken}`;
    }
    return new HttpHeaders(headerVals);
  }


  doGet(url: string, query = null, resJson = true) {
    return new Promise((resolve, reject) => {
      const headers = this.doHeaders(null);
      const finalUrl = this.doQueryString(CoreService.apiUrl + url, query);
      const promise = this.http.get(finalUrl, { headers: headers });
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

  doDelete(url: string, query = null, resJson = true) {
    return new Promise((resolve, reject) => {
      const headers = this.doHeaders(null);
      const finalUrl = this.doQueryString(CoreService.apiUrl + url, query);
      const promise = this.http.delete(finalUrl, { headers: headers });
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


  doPost(url: string, data: any, files: any = null) {
    return this.doSubmit('post', url, data, files);
  }

  doPut(url: string, data: any, files: any = null) {
    return this.doSubmit('put', url, data, files);
  }

  doSubmit(method: string, url: string, data: any, files: any = null) {
    return new Promise((resolve, reject) => {
      const headers = this.doHeaders(data);
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
      let prom;
      if (method === 'post') {
        prom = this.http.post(CoreService.apiUrl + url, formData, { headers: headers });
      } else {
        prom = this.http.put(CoreService.apiUrl + url, formData, { headers: headers });
      }
      return prom
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
        if (!key) {
          continue;
        }
        url += `&${key}=${queries[key]}`;
      }
    }
    return url;
  }

  setDataForm(form, keys, data) {
    if (!data) { return; }
    const formData = {};
    for (const key in keys) {
      if (key in data) {
        const value = data[key];
        formData[key] = value;
      } else { formData[key] = ''; }
    }
    // (<FormGroup>form).setValue(formData, { onlySelf: true });
    (<FormGroup>form).patchValue(formData, { onlySelf: true });
  }

}
